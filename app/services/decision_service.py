from sqlalchemy.orm import Session
from datetime import timedelta

from app.repositories.decision_repository import DecisionRepository
from app.repositories.product_repository import ProductRepository
from app.services.future_forecast_service import FutureForecastService


ANOMALY_LABELS = {
    "ABNORMAL_SALES_INCREASE": "Hausse anormale des ventes",
    "ABNORMAL_SALES_DECREASE": "Baisse anormale des ventes",
    "UNUSUAL_TRANSACTION": "Transaction inhabituelle",
    "PRICE_INCONSISTENCY": "Incohérence de prix",
    "POSSIBLE_DUPLICATE": "Doublon possible",
    "NEGATIVE_STOCK": "Stock négatif",
    "STOCKOUT": "Rupture de stock",
    "EXCESS_STOCK": "Excès de stock",
    "NO_SALES": "Absence de ventes",
    "UNUSUAL_DISCOUNT": "Remise inhabituelle",
}


class DecisionService:
    def __init__(self, db: Session):
        self.repository = DecisionRepository(db)
        self.product_repository = ProductRepository(db)
        self.future_forecast_service = FutureForecastService(db)

    @staticmethod
    def _risk_level(
        current_stock: float,
        predicted_quantity: float,
        upper_quantity: float,
        horizon: int,
    ) -> str:
        first_two_days_estimate = predicted_quantity * min(2, horizon) / horizon
        if current_stock <= first_two_days_estimate:
            return "CRITIQUE"
        if current_stock < predicted_quantity:
            return "ÉLEVÉ"
        if current_stock < upper_quantity:
            return "MOYEN"
        return "FAIBLE"

    def get_recommendations(self) -> list[dict]:
        recommendations = []

        for row in self.repository.get_latest_product_forecasts():
            predicted_quantity = float(row.get("predicted_p50") or row["predicted_quantity"])
            p80_quantity = float(row.get("predicted_p80") or predicted_quantity)
            p90_quantity = float(row.get("predicted_p90") or p80_quantity)
            uncertainty_buffer = max(0.0, p90_quantity - predicted_quantity)
            safety_stock = float(row.get("minimum_stock") or 0)
            upper_quantity = p90_quantity + safety_stock
            current_stock = float(row["current_stock"])
            recommended_order = max(0.0, upper_quantity - current_stock)
            historical_quantity = float(row["historical_quantity_7d"])
            forecast_daily = predicted_quantity / max(int(row["horizon"]), 1)
            historical_daily = historical_quantity / 7
            if historical_daily > 0:
                trend_percentage = (
                    (forecast_daily - historical_daily) / historical_daily * 100
                )
            else:
                trend_percentage = 100.0 if forecast_daily > 0 else 0.0
            days_of_cover = (
                current_stock / forecast_daily if forecast_daily > 0 else None
            )
            estimated_stockout_date = (
                row["forecast_start_date"] + timedelta(days=max(int(days_of_cover), 0))
                if days_of_cover is not None and days_of_cover < int(row["horizon"])
                else None
            )

            recommendations.append(
                {
                    **row,
                    "predicted_quantity": predicted_quantity,
                    "upper_quantity": upper_quantity,
                    "p80_quantity": p80_quantity,
                    "p90_quantity": p90_quantity,
                    "target_stock": upper_quantity,
                    "predicted_revenue": float(row["predicted_revenue"]),
                    "current_stock": current_stock,
                    "safety_stock": safety_stock,
                    "uncertainty_buffer": uncertainty_buffer,
                    "recommended_order": recommended_order,
                    "days_of_cover": days_of_cover,
                    "estimated_stockout_date": estimated_stockout_date,
                    "risk_level": self._risk_level(
                        current_stock,
                        predicted_quantity,
                        upper_quantity,
                        int(row["horizon"]),
                    ),
                    "trend_percentage": trend_percentage,
                }
            )

        risk_order = {"CRITIQUE": 0, "ÉLEVÉ": 1, "MOYEN": 2, "FAIBLE": 3}
        return sorted(
            recommendations,
            key=lambda item: (
                risk_order[item["risk_level"]],
                -item["recommended_order"],
            ),
        )

    def get_alerts(self, recommendations: list[dict] | None = None) -> list[dict]:
        recommendations = recommendations or self.get_recommendations()
        alerts = []

        for item in recommendations:
            if item["risk_level"] != "FAIBLE":
                alert_type = {
                    "CRITIQUE": "Risque critique de rupture",
                    "ÉLEVÉ": "Stock bientôt insuffisant",
                    "MOYEN": "Stock sous la borne de sécurité",
                }[item["risk_level"]]
                severity = {
                    "CRITIQUE": "CRITICAL",
                    "ÉLEVÉ": "HIGH",
                    "MOYEN": "MEDIUM",
                }[item["risk_level"]]
                alerts.append(
                    {
                        "date": item["forecast_start_date"],
                        "product_name": item["product_name"],
                        "category_name": item["category_name"],
                        "severity": severity,
                        "alert_type": alert_type,
                        "status": "OPEN",
                        "message": (
                            f"Commander environ "
                            f"{item['recommended_order']:.0f} colis."
                        ),
                    }
                )

            if item["trend_percentage"] >= 30:
                alerts.append(
                    {
                        "date": item["forecast_start_date"],
                        "product_name": item["product_name"],
                        "category_name": item["category_name"],
                        "severity": "HIGH",
                        "alert_type": "Forte hausse prévue des ventes",
                        "status": "OPEN",
                        "message": (
                            f"Demande journalière attendue en hausse de "
                            f"{item['trend_percentage']:.0f} %."
                        ),
                    }
                )
            elif item["trend_percentage"] <= -30:
                alerts.append(
                    {
                        "date": item["forecast_start_date"],
                        "product_name": item["product_name"],
                        "category_name": item["category_name"],
                        "severity": "MEDIUM",
                        "alert_type": "Baisse inhabituelle de la demande",
                        "status": "OPEN",
                        "message": (
                            f"Demande journalière attendue en baisse de "
                            f"{abs(item['trend_percentage']):.0f} %."
                        ),
                    }
                )

        for anomaly in self.repository.get_anomalies():
            alerts.append(
                {
                    "date": anomaly["anomaly_date"].date(),
                    "product_name": anomaly["product_name"],
                    "category_name": anomaly["category_name"],
                    "severity": anomaly["severity"],
                    "alert_type": ANOMALY_LABELS.get(
                        anomaly["anomaly_type"],
                        anomaly["anomaly_type"],
                    ),
                    "status": anomaly["status"],
                    "message": anomaly["description"],
                }
            )

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return sorted(
            alerts,
            key=lambda alert: (
                severity_order.get(alert["severity"], 4),
                -alert["date"].toordinal(),
            ),
        )

    def get_summary(self, recommendations: list[dict] | None = None) -> dict:
        recommendations = recommendations or self.get_recommendations()
        active_products = self.repository.get_active_product_count()

        return {
            "predicted_revenue": sum(
                item["predicted_revenue"] for item in recommendations
            ),
            "predicted_quantity": sum(
                item["predicted_quantity"] for item in recommendations
            ),
            "products_at_risk": sum(
                item["risk_level"] in {"CRITIQUE", "ÉLEVÉ", "MOYEN"}
                for item in recommendations
            ),
            "products_to_restock": sum(
                item["recommended_order"] > 0 for item in recommendations
            ),
            "forecasted_products": len(recommendations),
            "active_products": active_products,
        }

    def generate_missing_forecasts(self) -> dict:
        forecasted_ids = self.repository.get_forecasted_product_ids()
        products = self.product_repository.get_all_active_products()
        missing = [
            product for product in products if product["id"] not in forecasted_ids
        ]
        successes = []
        errors = []

        for product in missing:
            try:
                result = self.future_forecast_service.generate_and_save(
                    product["id"],
                    horizon=7,
                    test_days=60,
                )
                successes.append(result["forecast_number"])
            except Exception as exc:
                errors.append(
                    {"product": product["name"], "error": str(exc)}
                )

        return {
            "requested": len(missing),
            "successes": successes,
            "errors": errors,
        }
