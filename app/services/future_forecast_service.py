from time import perf_counter

from sqlalchemy.orm import Session

from app.ml.future import generate_iterative_forecast
from app.ml.models import FEATURE_COLUMNS, MODEL_LABELS, PREDICTION_COLUMNS
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.product_repository import ProductRepository
from app.services.forecast_service import ForecastService


class FutureForecastService:
    CONFIDENCE_LEVEL = 0.95
    CONFIDENCE_Z = 1.96

    def __init__(self, db: Session):
        self.db = db
        self.forecast_service = ForecastService(db)
        self.product_repository = ProductRepository(db)
        self.forecast_repository = ForecastRepository(db)

    def get_products(self) -> list[dict]:
        return self.forecast_service.get_products()

    def get_forecast_history(self) -> list[dict]:
        # Le service qualité met d'abord à jour les statuts et évalue les
        # prévisions arrivées à échéance.
        from app.services.ml_quality_service import MLQualityService

        return MLQualityService(self.db).get_dashboard_data()["history"]

    def get_forecast_results(self, forecast_id: str) -> list[dict]:
        return self.forecast_repository.get_forecast_results(forecast_id)

    def get_product_stock(self, product_id: str) -> dict:
        return self.product_repository.get_stock_snapshot(product_id)

    def generate_and_save(
        self,
        product_id: str,
        horizon: int = 7,
        test_days: int = 60,
        *,
        evaluation: dict | None = None,
        selected_model: str | None = None,
    ) -> dict:
        started_at = perf_counter()
        product = self.product_repository.get_by_id(product_id)
        evaluation = evaluation or self.forecast_service.evaluate_product(
            product_id, test_days
        )
        dataset = evaluation["dataset"]
        best_model = selected_model or evaluation["best_model"]
        if best_model not in evaluation["models"]:
            raise ValueError("Le modèle sélectionné n’est pas disponible pour ce produit.")
        best_metrics = evaluation["models"][best_model]

        test_data = evaluation["test_data"]
        eligible = ~(
            test_data["stockout_flag"].astype(bool)
            | (test_data["stock_available"] <= 0)
        )
        residuals = (
            test_data.loc[eligible, "quantity_sold"]
            - test_data.loc[
                eligible,
                PREDICTION_COLUMNS[best_model],
            ]
        )
        residual_std = float(residuals.std(ddof=1))
        if residual_std <= 0 or residuals.empty:
            residual_std = float(best_metrics["rmse"])
        residual_quantiles = {
            "p80": max(0.0, float(residuals.quantile(0.80))) if not residuals.empty else 0.0,
            "p90": max(0.0, float(residuals.quantile(0.90))) if not residuals.empty else 0.0,
        }

        future = generate_iterative_forecast(
            dataset=dataset,
            model_name=best_model,
            horizon=horizon,
            residual_std=residual_std,
            selling_price=product["selling_price"],
            confidence_z=self.CONFIDENCE_Z,
            residual_quantiles=residual_quantiles,
        )
        duration_seconds = perf_counter() - started_at

        persistence = self.forecast_repository.save_forecast(
            product_id=product_id,
            model_name=MODEL_LABELS[best_model],
            training_start_date=future["training_start_date"],
            training_end_date=future["training_end_date"],
            test_start_date=test_data["date"].min().date(),
            test_end_date=test_data["date"].max().date(),
            metrics=best_metrics,
            parameters={
                "product_id": product_id,
                "model_key": best_model,
                "features": FEATURE_COLUMNS,
                "horizon": horizon,
                "test_days": test_days,
                "confidence_level": self.CONFIDENCE_LEVEL,
                "iterative_lags": True,
                "stockout_policy": "exclude_from_training_and_metrics",
                "stock_feature": "opening_stock",
                "quantiles": [0.50, 0.80, 0.90],
                "quantile_method": (
                    "xgboost_quantile"
                    if best_model == "xgboost"
                    else "residual_distribution"
                ),
                "residual_quantiles": residual_quantiles,
            },
            duration_seconds=duration_seconds,
            forecast_data=future["forecast"],
        )

        return {
            "product": product,
            "best_model": best_model,
            "best_model_label": MODEL_LABELS[best_model],
            "metrics": best_metrics,
            "confidence_level": self.CONFIDENCE_LEVEL,
            "residual_std": residual_std,
            "history": dataset[["date", "quantity_sold"]].tail(60).copy(),
            "excluded_train_stockouts": evaluation[
                "excluded_train_stockouts"
            ],
            "excluded_test_stockouts": evaluation["excluded_test_stockouts"],
            **future,
            **persistence,
        }
