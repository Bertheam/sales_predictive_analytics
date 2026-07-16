from sqlalchemy import text
from sqlalchemy.orm import Session


class DecisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_product_forecasts(self) -> list[dict]:
        query = text("""
            WITH ranked_forecasts AS (
                SELECT
                    f.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY f.product_id
                        ORDER BY f.created_at DESC, f.id DESC
                    ) AS row_number
                FROM forecasts f
                WHERE f.status IN ('ACTIVE', 'EVALUATED', 'COMPLETED')
                  AND f.forecast_level = 'PRODUCT'
            ),
            latest_forecasts AS (
                SELECT *
                FROM ranked_forecasts
                WHERE row_number = 1
            ),
            forecast_totals AS (
                SELECT
                    fr.forecast_id,
                    SUM(fr.predicted_quantity) AS predicted_quantity,
                    SUM(fr.lower_bound) AS lower_quantity,
                    SUM(fr.upper_bound) AS upper_quantity,
                    SQRT(
                        SUM(
                            POWER(
                                GREATEST(
                                    fr.upper_bound - fr.predicted_quantity,
                                    0
                                ),
                                2
                            )
                        )
                    ) AS confidence_safety_stock,
                    SUM(fr.predicted_revenue) AS predicted_revenue,
                    SUM(fr.recommended_stock) AS persisted_stock_need
                FROM forecast_results fr
                GROUP BY fr.forecast_id
            )
            SELECT
                p.id AS product_id,
                p.code AS product_code,
                p.name AS product_name,
                pc.name AS category_name,
                lf.id AS forecast_id,
                lf.forecast_number,
                lf.horizon,
                lf.forecast_start_date,
                lf.forecast_end_date,
                lf.created_at AS forecast_created_at,
                mr.model_name,
                COALESCE(ft.predicted_quantity, 0) AS predicted_quantity,
                COALESCE(ft.lower_quantity, 0) AS lower_quantity,
                COALESCE(ft.upper_quantity, 0) AS upper_quantity,
                COALESCE(ft.confidence_safety_stock, 0)
                    AS confidence_safety_stock,
                COALESCE(ft.predicted_revenue, 0) AS predicted_revenue,
                COALESCE(ft.persisted_stock_need, 0) AS persisted_stock_need,
                COALESCE(stock.closing_stock, 0) AS current_stock,
                COALESCE(history.quantity_sold, 0) AS historical_quantity_7d
            FROM latest_forecasts lf
            JOIN products p ON p.id = lf.product_id
            JOIN product_categories pc ON pc.id = p.category_id
            LEFT JOIN model_runs mr ON mr.id = lf.model_run_id
            LEFT JOIN forecast_totals ft ON ft.forecast_id = lf.id
            LEFT JOIN LATERAL (
                SELECT ds.closing_stock
                FROM daily_stocks ds
                WHERE ds.product_id = p.id
                ORDER BY ds.stock_date DESC
                LIMIT 1
            ) stock ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(si.quantity_packages) AS quantity_sold
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE si.product_id = p.id
                  AND s.sale_date BETWEEN
                      (SELECT MAX(sale_date) FROM sales) - 6
                      AND (SELECT MAX(sale_date) FROM sales)
            ) history ON TRUE
            ORDER BY p.name
        """)

        return [dict(row) for row in self.db.execute(query).mappings()]

    def get_anomalies(self) -> list[dict]:
        query = text("""
            SELECT
                a.id,
                a.anomaly_date,
                a.anomaly_type,
                a.severity,
                a.status,
                a.description,
                p.id AS product_id,
                COALESCE(p.name, 'Global') AS product_name,
                COALESCE(pc.name, 'Toutes catégories') AS category_name
            FROM anomalies a
            LEFT JOIN products p ON p.id = a.product_id
            LEFT JOIN product_categories pc ON pc.id = p.category_id
            ORDER BY a.anomaly_date DESC
        """)

        return [dict(row) for row in self.db.execute(query).mappings()]

    def get_active_product_count(self) -> int:
        return int(
            self.db.execute(
                text("SELECT COUNT(*) FROM products WHERE is_active = TRUE")
            ).scalar_one()
        )

    def get_forecasted_product_ids(self) -> set[str]:
        rows = self.db.execute(
            text("""
                SELECT DISTINCT product_id
                FROM forecasts
                WHERE status IN ('ACTIVE', 'EVALUATED', 'COMPLETED')
                  AND forecast_level = 'PRODUCT'
            """)
        )
        return {str(row.product_id) for row in rows}
