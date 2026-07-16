from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_available_date_range(self):
        query = text("""
            SELECT
                MIN(sale_date) AS min_date,
                MAX(sale_date) AS max_date
            FROM sales
        """)

        return self.db.execute(query).mappings().one()

    def get_total_revenue(
        self,
        start_date: date,
        end_date: date,
    ) -> float:
        query = text("""
            SELECT COALESCE(SUM(total_amount), 0)
            FROM sales
            WHERE sale_date BETWEEN :start_date AND :end_date
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalar()

        return float(result or 0)

    def get_total_sales(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        query = text("""
            SELECT COUNT(*)
            FROM sales
            WHERE sale_date BETWEEN :start_date AND :end_date
        """)

        return int(
            self.db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ).scalar()
            or 0
        )

    def get_active_customers(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        query = text("""
            SELECT COUNT(DISTINCT customer_id)
            FROM sales
            WHERE sale_date BETWEEN :start_date AND :end_date
        """)

        return int(
            self.db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ).scalar()
            or 0
        )

    def get_sold_products(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        query = text("""
            SELECT COUNT(DISTINCT si.product_id)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.sale_date BETWEEN :start_date AND :end_date
        """)

        return int(
            self.db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ).scalar()
            or 0
        )

    def get_total_anomalies(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        query = text("""
            SELECT COUNT(*)
            FROM anomalies
            WHERE anomaly_date::date BETWEEN :start_date AND :end_date
        """)

        return int(
            self.db.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ).scalar()
            or 0
        )

    def get_total_quantity_sold(
        self,
        start_date: date,
        end_date: date,
    ) -> float:
        query = text("""
            SELECT COALESCE(SUM(si.quantity_packages), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.sale_date BETWEEN :start_date AND :end_date
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalar()

        return float(result or 0)

    def get_revenue_evolution(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        query = text("""
            SELECT
                sale_date,
                SUM(total_amount) AS revenue
            FROM sales
            WHERE sale_date BETWEEN :start_date AND :end_date
            GROUP BY sale_date
            ORDER BY sale_date
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [
            {
                "date": row.sale_date,
                "revenue": float(row.revenue or 0),
            }
            for row in result
        ]

    def get_top_products(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> list[dict]:
        query = text("""
            SELECT
                p.name AS product_name,
                SUM(si.quantity_packages) AS quantity_sold,
                SUM(si.total_amount) AS revenue
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.sale_date BETWEEN :start_date AND :end_date
            GROUP BY p.id, p.name
            ORDER BY quantity_sold DESC
            LIMIT :limit
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )

        return [
            {
                "product_name": row.product_name,
                "quantity_sold": float(row.quantity_sold or 0),
                "revenue": float(row.revenue or 0),
            }
            for row in result
        ]

    def get_sales_by_category(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        query = text("""
            SELECT
                pc.name AS category_name,
                SUM(si.quantity_packages) AS quantity_sold,
                SUM(si.total_amount) AS revenue
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            JOIN product_categories pc ON pc.id = p.category_id
            WHERE s.sale_date BETWEEN :start_date AND :end_date
            GROUP BY pc.id, pc.name
            ORDER BY revenue DESC
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [
            {
                "category_name": row.category_name,
                "quantity_sold": float(row.quantity_sold or 0),
                "revenue": float(row.revenue or 0),
            }
            for row in result
        ]

    def get_sales_by_customer_type(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        query = text("""
            SELECT
                ct.name AS customer_type,
                COUNT(DISTINCT s.id) AS sales_count,
                SUM(s.total_amount) AS revenue
            FROM sales s
            JOIN customers c ON c.id = s.customer_id
            JOIN customer_types ct ON ct.id = c.customer_type_id
            WHERE s.sale_date BETWEEN :start_date AND :end_date
            GROUP BY ct.id, ct.name
            ORDER BY revenue DESC
        """)

        result = self.db.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        return [
            {
                "customer_type": row.customer_type,
                "sales_count": int(row.sales_count or 0),
                "revenue": float(row.revenue or 0),
            }
            for row in result
        ]
