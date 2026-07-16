from datetime import date

from sqlalchemy.orm import Session

from app.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, db: Session):
        self.repository = DashboardRepository(db)

    def get_available_date_range(self):
        return self.repository.get_available_date_range()

    def get_statistics(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        return {
            "total_revenue": self.repository.get_total_revenue(
                start_date,
                end_date,
            ),
            "total_sales": self.repository.get_total_sales(
                start_date,
                end_date,
            ),
            "active_customers": self.repository.get_active_customers(
                start_date,
                end_date,
            ),
            "sold_products": self.repository.get_sold_products(
                start_date,
                end_date,
            ),
            "total_quantity_sold": self.repository.get_total_quantity_sold(
                start_date,
                end_date,
            ),
            "total_anomalies": self.repository.get_total_anomalies(
                start_date,
                end_date,
            ),
        }

    def get_dashboard_analysis(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        return {
            "revenue_evolution": self.repository.get_revenue_evolution(
                start_date,
                end_date,
            ),
            "top_products": self.repository.get_top_products(
                start_date,
                end_date,
            ),
            "sales_by_category": self.repository.get_sales_by_category(
                start_date,
                end_date,
            ),
            "sales_by_customer_type": (
                self.repository.get_sales_by_customer_type(
                    start_date,
                    end_date,
                )
            ),
        }
