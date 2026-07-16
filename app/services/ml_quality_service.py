from collections import defaultdict

from sqlalchemy.orm import Session

from app.ml.models import MODEL_LABELS
from app.ml.monitoring import calculate_drift, evaluate_forecast_rows
from app.repositories.ml_quality_repository import MLQualityRepository
from app.repositories.product_repository import ProductRepository
from app.services.forecast_service import ForecastService


PERFORMANCE_LABELS = {
    "GOOD": "Bonne",
    "WATCH": "À surveiller",
    "POOR": "Insuffisante",
}
DRIFT_LABELS = {
    "DECLINING": "En baisse",
    "IMPROVING": "En amélioration",
    "STABLE": "Stable",
    "INSUFFICIENT_DATA": "Données insuffisantes",
}


class MLQualityService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MLQualityRepository(db)
        self.product_repository = ProductRepository(db)
        self.forecast_service = ForecastService(db)

    def refresh_forecast_lifecycle(self) -> dict:
        cutoff_date = self.repository.get_data_cutoff_date()
        if cutoff_date is None:
            return {"cutoff_date": None, "evaluated": 0}

        try:
            self.repository.sync_forecast_statuses(cutoff_date)
            expired = self.repository.get_expired_forecasts()
            evaluated = 0

            for forecast in expired:
                rows = self.repository.get_forecast_actual_rows(forecast["id"])
                evaluation = evaluate_forecast_rows(rows)
                self.repository.save_evaluation(forecast, evaluation)
                evaluated += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "cutoff_date": cutoff_date,
            "evaluated": evaluated,
        }

    def get_forecast_history(self) -> list[dict]:
        return self.repository.get_forecast_history()

    def get_quality_by_product(self) -> list[dict]:
        history = [
            row
            for row in self.repository.get_forecast_history()
            if row["status"] == "EVALUATED" and row["mae"] is not None
        ]
        grouped = defaultdict(list)
        for row in history:
            grouped[(str(row["product_id"]), row["model_name"])].append(row)

        quality_rows = []
        for (product_id, model_name), evaluations in grouped.items():
            evaluations.sort(key=lambda row: row["forecast_end_date"])
            latest = evaluations[-1]
            drift = calculate_drift(evaluations)
            performance_status = latest["performance_status"]

            if (
                performance_status == "POOR"
                or drift["drift_status"] == "DECLINING"
            ):
                action = "Réentraîner / comparer les modèles"
            elif performance_status == "WATCH":
                action = "Surveiller les prochaines prévisions"
            else:
                action = "Aucune action immédiate"

            quality_rows.append(
                {
                    "product_id": product_id,
                    "product_name": latest["product_name"],
                    "model_name": model_name,
                    "forecast_count": len(evaluations),
                    "mae": float(latest["mae"]),
                    "rmse": float(latest["rmse"]),
                    "mape": (
                        float(latest["mape"])
                        if latest["mape"] is not None
                        else None
                    ),
                    "performance_status": performance_status,
                    "performance_label": PERFORMANCE_LABELS.get(
                        performance_status,
                        performance_status,
                    ),
                    "drift_status": drift["drift_status"],
                    "drift_label": DRIFT_LABELS[drift["drift_status"]],
                    "current_mae_30d": drift["current_mae"],
                    "previous_mae_30d": drift["previous_mae"],
                    "action": action,
                }
            )

        return sorted(
            quality_rows,
            key=lambda row: (
                row["action"] != "Réentraîner / comparer les modèles",
                -row["mae"],
            ),
        )

    def get_dashboard_data(self) -> dict:
        lifecycle = self.refresh_forecast_lifecycle()
        history = self.repository.get_forecast_history()
        quality = self.get_quality_by_product()
        status_counts = self.repository.get_status_counts()
        evaluated_rows = [row for row in history if row["status"] == "EVALUATED"]

        return {
            "lifecycle": lifecycle,
            "history": history,
            "quality": quality,
            "reviews": self.repository.get_model_reviews(),
            "status_counts": status_counts,
            "total_forecasts": len(history),
            "evaluated_forecasts": len(evaluated_rows),
            "average_mae": (
                sum(float(row["mae"]) for row in evaluated_rows)
                / len(evaluated_rows)
                if evaluated_rows
                else None
            ),
            "average_mape": (
                sum(
                    float(row["mape"])
                    for row in evaluated_rows
                    if row["mape"] is not None
                )
                / sum(row["mape"] is not None for row in evaluated_rows)
                if any(row["mape"] is not None for row in evaluated_rows)
                else None
            ),
            "models_to_review": sum(
                row["action"] == "Réentraîner / comparer les modèles"
                for row in quality
            ),
        }

    def run_periodic_reassessment(self, all_products: bool = False) -> dict:
        quality = self.get_quality_by_product()
        previous_models = {
            row["product_id"]: row["model_name"] for row in quality
        }

        if all_products:
            products = self.product_repository.get_all_active_products()
        else:
            ids_to_review = {
                row["product_id"]
                for row in quality
                if row["action"] == "Réentraîner / comparer les modèles"
            }
            products = [
                product
                for product in self.product_repository.get_all_active_products()
                if product["id"] in ids_to_review
            ]

        cutoff_date = self.repository.get_data_cutoff_date()
        successes = []
        errors = []

        for product in products:
            try:
                evaluation = self.forecast_service.evaluate_product(
                    product["id"],
                    test_days=60,
                )
                best_model = evaluation["best_model"]
                recommended_model = MODEL_LABELS[best_model]
                previous_model = previous_models.get(product["id"])
                action = (
                    "CHANGER_MODELE"
                    if previous_model and previous_model != recommended_model
                    else "CONSERVER_MODELE"
                )
                test_data = evaluation["test_data"]
                self.repository.save_model_review(
                    product_id=product["id"],
                    review_date=cutoff_date,
                    period_start_date=test_data["date"].min().date(),
                    period_end_date=test_data["date"].max().date(),
                    previous_model=previous_model,
                    recommended_model=recommended_model,
                    metrics=evaluation["models"],
                    action=action,
                )
                successes.append(product["name"])
            except Exception as exc:
                errors.append({"product": product["name"], "error": str(exc)})

        if successes:
            self.db.commit()

        return {
            "requested": len(products),
            "successes": successes,
            "errors": errors,
        }
