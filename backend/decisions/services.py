from app.database.session import session_for_company
from app.services.decision_service import DecisionService


def load_decision_center(company_id):
    with session_for_company(company_id) as db:
        service = DecisionService(db)
        recommendations = service.get_recommendations()
        return {
            "recommendations": recommendations,
            "alerts": service.get_alerts(recommendations),
            "summary": service.get_summary(recommendations),
        }


def load_restock_product(company_id, product_id):
    with session_for_company(company_id) as db:
        service = DecisionService(db)
        recommendation = next(
            (row for row in service.get_recommendations() if str(row["product_id"]) == str(product_id)),
            None,
        )
        return recommendation, service.repository.get_active_suppliers()
