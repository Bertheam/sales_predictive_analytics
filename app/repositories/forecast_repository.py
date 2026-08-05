import json
from datetime import datetime
from uuid import uuid4

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


class ForecastRepository:
    """Persiste une prévision complète dans une transaction unique."""

    def __init__(self, db: Session):
        self.db = db

    def save_forecast(
        self,
        *,
        product_id: str,
        model_name: str,
        training_start_date,
        training_end_date,
        test_start_date,
        test_end_date,
        metrics: dict,
        parameters: dict,
        duration_seconds: float,
        forecast_data: pd.DataFrame,
    ) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        suffix = uuid4().hex[:8].upper()
        run_number = f"MR-{timestamp}-{suffix}"
        forecast_number = f"FC-{timestamp}-{suffix}"

        try:
            model_run_id = self.db.execute(
                text("""
                    INSERT INTO model_runs (
                        run_number,
                        model_name,
                        model_version,
                        target_variable,
                        forecast_level,
                        training_start_date,
                        training_end_date,
                        test_start_date,
                        test_end_date,
                        parameters,
                        mae,
                        rmse,
                        mape,
                        training_duration_seconds,
                        status
                    ) VALUES (
                        :run_number,
                        :model_name,
                        '1.0',
                        'quantity_packages',
                        'PRODUCT',
                        :training_start_date,
                        :training_end_date,
                        :test_start_date,
                        :test_end_date,
                        CAST(:parameters AS JSONB),
                        :mae,
                        :rmse,
                        :mape,
                        :duration_seconds,
                        'ACTIVE'
                    )
                    RETURNING id
                """),
                {
                    "run_number": run_number,
                    "model_name": model_name,
                    "training_start_date": training_start_date,
                    "training_end_date": training_end_date,
                    "test_start_date": test_start_date,
                    "test_end_date": test_end_date,
                    "parameters": json.dumps(parameters),
                    "mae": metrics["mae"],
                    "rmse": metrics["rmse"],
                    "mape": metrics["mape"],
                    "duration_seconds": duration_seconds,
                },
            ).scalar_one()

            forecast_id = self.db.execute(
                text("""
                    INSERT INTO forecasts (
                        forecast_number,
                        forecast_level,
                        product_id,
                        forecast_frequency,
                        horizon,
                        training_start_date,
                        training_end_date,
                        forecast_start_date,
                        forecast_end_date,
                        model_run_id,
                        status
                    ) VALUES (
                        :forecast_number,
                        'PRODUCT',
                        :product_id,
                        'DAILY',
                        :horizon,
                        :training_start_date,
                        :training_end_date,
                        :forecast_start_date,
                        :forecast_end_date,
                        :model_run_id,
                        'COMPLETED'
                    )
                    RETURNING id
                """),
                {
                    "forecast_number": forecast_number,
                    "product_id": product_id,
                    "horizon": len(forecast_data),
                    "training_start_date": training_start_date,
                    "training_end_date": training_end_date,
                    "forecast_start_date": forecast_data["date"].min().date(),
                    "forecast_end_date": forecast_data["date"].max().date(),
                    "model_run_id": model_run_id,
                },
            ).scalar_one()

            insert_result = text("""
                INSERT INTO forecast_results (
                    forecast_id,
                    forecast_date,
                    predicted_quantity,
                    lower_bound,
                    upper_bound,
                    predicted_p50,
                    predicted_p80,
                    predicted_p90,
                    predicted_revenue,
                    recommended_stock
                ) VALUES (
                    :forecast_id,
                    :forecast_date,
                    :predicted_quantity,
                    :lower_bound,
                    :upper_bound,
                    :predicted_p50,
                    :predicted_p80,
                    :predicted_p90,
                    :predicted_revenue,
                    :recommended_stock
                )
            """)
            for row in forecast_data.to_dict("records"):
                self.db.execute(
                    insert_result,
                    {
                        "forecast_id": forecast_id,
                        "forecast_date": pd.Timestamp(row["date"]).date(),
                        "predicted_quantity": float(row["predicted_quantity"]),
                        "lower_bound": float(row["lower_bound"]),
                        "upper_bound": float(row["upper_bound"]),
                        "predicted_p50": float(row.get("predicted_p50", row["predicted_quantity"])),
                        "predicted_p80": float(row.get("predicted_p80", row["upper_bound"])),
                        "predicted_p90": float(row.get("predicted_p90", row["upper_bound"])),
                        "predicted_revenue": float(row["predicted_revenue"]),
                        "recommended_stock": float(row["stock_need"]),
                    },
                )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "model_run_id": str(model_run_id),
            "run_number": run_number,
            "forecast_id": str(forecast_id),
            "forecast_number": forecast_number,
        }

    def get_forecast_results(self, forecast_id: str) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    fr.forecast_date,
                    fr.predicted_quantity,
                    fr.lower_bound,
                    fr.upper_bound,
                    fr.predicted_p50,
                    fr.predicted_p80,
                    fr.predicted_p90,
                    fr.predicted_revenue,
                    fr.recommended_stock,
                    fre.actual_quantity,
                    fre.absolute_error
                FROM forecast_results fr
                LEFT JOIN forecast_result_evaluations fre
                    ON fre.forecast_result_id = fr.id
                WHERE fr.forecast_id = :forecast_id
                ORDER BY fr.forecast_date
            """),
            {"forecast_id": forecast_id},
        )
        return [dict(row) for row in rows.mappings()]
