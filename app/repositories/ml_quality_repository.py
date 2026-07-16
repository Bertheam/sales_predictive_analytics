import json

from sqlalchemy import text
from sqlalchemy.orm import Session


class MLQualityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_data_cutoff_date(self):
        return self.db.execute(
            text("SELECT MAX(sale_date) FROM sales")
        ).scalar_one()

    def sync_forecast_statuses(self, cutoff_date) -> None:
        self.db.execute(
            text("""
                UPDATE forecasts f
                SET
                    status = 'EVALUATED',
                    status_updated_at = NOW()
                WHERE EXISTS (
                    SELECT 1
                    FROM forecast_evaluations fe
                    WHERE fe.forecast_id = f.id
                )
            """)
        )
        self.db.execute(
            text("""
                UPDATE forecasts f
                SET
                    status = 'EXPIRED',
                    status_updated_at = NOW()
                WHERE f.forecast_end_date <= :cutoff_date
                  AND NOT EXISTS (
                      SELECT 1
                      FROM forecast_evaluations fe
                      WHERE fe.forecast_id = f.id
                  )
            """),
            {"cutoff_date": cutoff_date},
        )
        self.db.execute(
            text("""
                UPDATE forecasts f
                SET
                    status = 'ACTIVE',
                    status_updated_at = NOW()
                WHERE f.forecast_end_date > :cutoff_date
                  AND NOT EXISTS (
                      SELECT 1
                      FROM forecast_evaluations fe
                      WHERE fe.forecast_id = f.id
                  )
            """),
            {"cutoff_date": cutoff_date},
        )

    def get_expired_forecasts(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT id, product_id, model_run_id
                FROM forecasts
                WHERE status = 'EXPIRED'
                ORDER BY forecast_end_date
            """)
        )
        return [dict(row) for row in rows.mappings()]

    def get_forecast_actual_rows(self, forecast_id) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    fr.id AS forecast_result_id,
                    fr.forecast_id,
                    fr.forecast_date,
                    fr.predicted_quantity,
                    COALESCE(SUM(si.quantity_packages), 0) AS actual_quantity
                FROM forecast_results fr
                JOIN forecasts f ON f.id = fr.forecast_id
                LEFT JOIN sales s ON s.sale_date = fr.forecast_date
                LEFT JOIN sale_items si
                    ON si.sale_id = s.id
                   AND si.product_id = f.product_id
                WHERE fr.forecast_id = :forecast_id
                GROUP BY
                    fr.id,
                    fr.forecast_id,
                    fr.forecast_date,
                    fr.predicted_quantity
                ORDER BY fr.forecast_date
            """),
            {"forecast_id": forecast_id},
        )
        return [dict(row) for row in rows.mappings()]

    def save_evaluation(
        self,
        forecast: dict,
        evaluation: dict,
    ) -> None:
        daily_query = text("""
            INSERT INTO forecast_result_evaluations (
                forecast_result_id,
                forecast_id,
                actual_quantity,
                absolute_error,
                squared_error,
                absolute_percentage_error
            ) VALUES (
                :forecast_result_id,
                :forecast_id,
                :actual_quantity,
                :absolute_error,
                :squared_error,
                :absolute_percentage_error
            )
            ON CONFLICT (forecast_result_id) DO UPDATE SET
                actual_quantity = EXCLUDED.actual_quantity,
                absolute_error = EXCLUDED.absolute_error,
                squared_error = EXCLUDED.squared_error,
                absolute_percentage_error = EXCLUDED.absolute_percentage_error,
                evaluated_at = NOW()
        """)
        for row in evaluation["daily"]:
            self.db.execute(
                daily_query,
                {
                    "forecast_result_id": row["forecast_result_id"],
                    "forecast_id": row["forecast_id"],
                    "actual_quantity": float(row["actual_quantity"]),
                    "absolute_error": float(row["absolute_error"]),
                    "squared_error": float(row["squared_error"]),
                    "absolute_percentage_error": (
                        None
                        if row["absolute_percentage_error"] != row["absolute_percentage_error"]
                        else float(row["absolute_percentage_error"])
                    ),
                },
            )

        self.db.execute(
            text("""
                INSERT INTO forecast_evaluations (
                    forecast_id,
                    product_id,
                    model_run_id,
                    predicted_quantity,
                    actual_quantity,
                    absolute_error,
                    mae,
                    rmse,
                    mape,
                    performance_status
                ) VALUES (
                    :forecast_id,
                    :product_id,
                    :model_run_id,
                    :predicted_quantity,
                    :actual_quantity,
                    :absolute_error,
                    :mae,
                    :rmse,
                    :mape,
                    :performance_status
                )
                ON CONFLICT (forecast_id) DO UPDATE SET
                    predicted_quantity = EXCLUDED.predicted_quantity,
                    actual_quantity = EXCLUDED.actual_quantity,
                    absolute_error = EXCLUDED.absolute_error,
                    mae = EXCLUDED.mae,
                    rmse = EXCLUDED.rmse,
                    mape = EXCLUDED.mape,
                    performance_status = EXCLUDED.performance_status,
                    evaluated_at = NOW()
            """),
            {
                "forecast_id": forecast["id"],
                "product_id": forecast["product_id"],
                "model_run_id": forecast["model_run_id"],
                "predicted_quantity": evaluation["predicted_quantity"],
                "actual_quantity": evaluation["actual_quantity"],
                "absolute_error": evaluation["absolute_error"],
                "mae": evaluation["mae"],
                "rmse": evaluation["rmse"],
                "mape": evaluation["mape"],
                "performance_status": evaluation["performance_status"],
            },
        )
        self.db.execute(
            text("""
                UPDATE forecasts
                SET
                    status = 'EVALUATED',
                    evaluated_at = NOW(),
                    status_updated_at = NOW()
                WHERE id = :forecast_id
            """),
            {"forecast_id": forecast["id"]},
        )

    def get_forecast_history(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    f.id,
                    f.forecast_number,
                    f.status,
                    f.forecast_start_date,
                    f.forecast_end_date,
                    f.horizon,
                    f.created_at,
                    p.id AS product_id,
                    p.name AS product_name,
                    pc.name AS category_name,
                    mr.model_name,
                    COALESCE(
                        fe.predicted_quantity,
                        totals.predicted_quantity,
                        0
                    ) AS predicted_quantity,
                    fe.actual_quantity,
                    fe.absolute_error,
                    fe.mae,
                    fe.rmse,
                    fe.mape,
                    fe.performance_status,
                    fe.evaluated_at
                FROM forecasts f
                JOIN products p ON p.id = f.product_id
                JOIN product_categories pc ON pc.id = p.category_id
                LEFT JOIN model_runs mr ON mr.id = f.model_run_id
                LEFT JOIN forecast_evaluations fe ON fe.forecast_id = f.id
                LEFT JOIN LATERAL (
                    SELECT SUM(predicted_quantity) AS predicted_quantity
                    FROM forecast_results fr
                    WHERE fr.forecast_id = f.id
                ) totals ON TRUE
                ORDER BY f.created_at DESC
            """)
        )
        return [dict(row) for row in rows.mappings()]

    def get_status_counts(self) -> dict:
        rows = self.db.execute(
            text("""
                SELECT status, COUNT(*) AS total
                FROM forecasts
                GROUP BY status
            """)
        )
        return {row.status: int(row.total) for row in rows}

    def save_model_review(
        self,
        *,
        product_id: str,
        review_date,
        period_start_date,
        period_end_date,
        previous_model: str | None,
        recommended_model: str,
        metrics: dict,
        action: str,
    ) -> None:
        self.db.execute(
            text("""
                INSERT INTO model_performance_reviews (
                    product_id,
                    review_date,
                    period_start_date,
                    period_end_date,
                    previous_model,
                    recommended_model,
                    metrics,
                    action
                ) VALUES (
                    :product_id,
                    :review_date,
                    :period_start_date,
                    :period_end_date,
                    :previous_model,
                    :recommended_model,
                    CAST(:metrics AS JSONB),
                    :action
                )
            """),
            {
                "product_id": product_id,
                "review_date": review_date,
                "period_start_date": period_start_date,
                "period_end_date": period_end_date,
                "previous_model": previous_model,
                "recommended_model": recommended_model,
                "metrics": json.dumps(metrics),
                "action": action,
            },
        )

    def get_model_reviews(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    mpr.*,
                    p.name AS product_name
                FROM model_performance_reviews mpr
                JOIN products p ON p.id = mpr.product_id
                ORDER BY mpr.created_at DESC
            """)
        )
        return [dict(row) for row in rows.mappings()]
