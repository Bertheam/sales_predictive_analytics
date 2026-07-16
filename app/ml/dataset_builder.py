from uuid import UUID

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


class SalesDatasetBuilder:
    """Construit une série journalière complète pour un produit."""

    def __init__(self, db: Session):
        self.db = db

    def get_products(self) -> list[dict]:
        query = text("""
            SELECT id, code, name
            FROM products
            WHERE is_active = TRUE
            ORDER BY name
        """)

        return [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
            }
            for row in self.db.execute(query)
        ]

    def get_available_date_range(self) -> dict:
        query = text("""
            SELECT
                MIN(sale_date) AS min_date,
                MAX(sale_date) AS max_date
            FROM sales
        """)

        return dict(self.db.execute(query).mappings().one())

    def build_product_daily_dataset(
        self,
        product_id: UUID | str,
    ) -> pd.DataFrame:
        date_range = self.get_available_date_range()
        min_date = date_range["min_date"]
        max_date = date_range["max_date"]

        if min_date is None or max_date is None:
            return pd.DataFrame(
                columns=[
                    "date",
                    "quantity_sold",
                    "revenue",
                    "sales_count",
                ]
            )

        query = text("""
            SELECT
                s.sale_date AS date,
                SUM(si.quantity_packages) AS quantity_sold,
                SUM(si.total_amount) AS revenue,
                COUNT(DISTINCT s.id) AS sales_count
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE si.product_id = :product_id
              AND s.sale_date BETWEEN :start_date AND :end_date
            GROUP BY s.sale_date
            ORDER BY s.sale_date
        """)

        rows = self.db.execute(
            query,
            {
                "product_id": product_id,
                "start_date": min_date,
                "end_date": max_date,
            },
        ).mappings()

        sales = pd.DataFrame(rows)
        calendar = pd.DataFrame(
            {"date": pd.date_range(min_date, max_date, freq="D")}
        )

        if sales.empty:
            dataset = calendar
            dataset["quantity_sold"] = 0.0
            dataset["revenue"] = 0.0
            dataset["sales_count"] = 0
        else:
            sales["date"] = pd.to_datetime(sales["date"])
            dataset = calendar.merge(sales, on="date", how="left")

        numeric_columns = ["quantity_sold", "revenue", "sales_count"]
        dataset[numeric_columns] = dataset[numeric_columns].fillna(0)
        dataset["quantity_sold"] = dataset["quantity_sold"].astype(float)
        dataset["revenue"] = dataset["revenue"].astype(float)
        dataset["sales_count"] = dataset["sales_count"].astype(int)

        return dataset

    def build_product_daily_sales(
        self,
        product_id: UUID | str,
    ) -> pd.DataFrame:
        """Alias conservé pour le futur pipeline de prévision."""
        return self.build_product_daily_dataset(product_id)

    def get_calendar_features(self) -> pd.DataFrame:
        query = text("""
            SELECT
                calendar_date AS date,
                day_of_week,
                week_number,
                month_number,
                quarter_number,
                is_weekend,
                is_public_holiday,
                is_ramadan_period,
                is_tabaski_period,
                is_end_of_month,
                is_start_of_month,
                temperature_average,
                rainfall
            FROM calendar_features
            ORDER BY calendar_date
        """)

        data = pd.DataFrame(self.db.execute(query).mappings())
        if not data.empty:
            data["date"] = pd.to_datetime(data["date"])
        return data

    def get_stock_features(self, product_id: UUID) -> pd.DataFrame:
        query = text("""
            SELECT
                stock_date AS date,
                opening_stock,
                quantity_received,
                quantity_damaged,
                closing_stock,
                minimum_stock,
                stockout_flag
            FROM daily_stocks
            WHERE product_id = :product_id
            ORDER BY stock_date
        """)

        data = pd.DataFrame(
            self.db.execute(query, {"product_id": product_id}).mappings()
        )
        if not data.empty:
            data["date"] = pd.to_datetime(data["date"])
        return data
