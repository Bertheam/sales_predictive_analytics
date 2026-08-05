from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Membership
from app.repositories.decision_repository import DecisionRepository
from app.repositories.product_repository import ProductRepository

from .models import RestockDraft


def recommendation(product_id=None):
    return {
        "product_id": product_id or uuid4(), "product_code": "PRD-001",
        "product_name": "Cola 50 cl", "category_name": "Boisson gazeuse",
        "forecast_id": uuid4(), "forecast_number": "PREV-001", "horizon": 7,
        "forecast_start_date": date.today(), "forecast_end_date": date.today(),
        "model_name": "Moyenne mobile", "predicted_quantity": 100.0,
        "p80_quantity": 115.0, "p90_quantity": 125.0,
        "predicted_revenue": 100000.0, "current_stock": 40.0,
        "safety_stock": 25.0, "uncertainty_buffer": 25.0,
        "recommended_order": 85.0, "risk_level": "CRITIQUE",
        "trend_percentage": 20.0, "days_of_cover": 2.8,
        "estimated_stockout_date": date.today(),
    }


class DecisionCenterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner-decision@example.com", password="A-secure-password-2026")
        self.company = Company.objects.create(code="decision-depot", name="Dépôt Décision")
        self.membership = Membership.objects.create(user=self.user, company=self.company, role=Membership.Role.OWNER)
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

    @patch("decisions.views.load_decision_center")
    def test_center_is_business_friendly(self, load):
        item = recommendation()
        load.return_value = {
            "recommendations": [item],
            "alerts": [{"alert_type": "Risque critique", "severity": "CRITICAL", "product_name": item["product_name"], "message": "Commander 85 colis."}],
            "summary": {"predicted_quantity": 100, "predicted_revenue": 100000, "products_at_risk": 1, "products_to_restock": 1, "forecasted_products": 1, "active_products": 1},
        }
        response = self.client.get(reverse("decisions:center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commandez au bon moment")
        self.assertContains(response, "85 colis")

    @patch("decisions.views.load_restock_product")
    def test_owner_can_prepare_tenant_scoped_draft(self, load):
        product_id = uuid4()
        item = recommendation(product_id)
        supplier_id = uuid4()
        load.return_value = (item, [{"id": supplier_id, "code": "FRS-001", "name": "Grossiste Test", "city": "Bamako"}])
        response = self.client.post(reverse("decisions:prepare", args=[product_id]), {"supplier_id": str(supplier_id), "quantity": "85"})
        self.assertRedirects(response, reverse("decisions:product-detail", args=[product_id]), fetch_redirect_response=False)
        draft = RestockDraft.objects.get()
        self.assertEqual(draft.company, self.company)
        self.assertEqual(draft.product_id, product_id)
        self.assertEqual(draft.supplier_name, "Grossiste Test")

    @patch("decisions.views.load_restock_product")
    def test_viewer_cannot_prepare_draft(self, load):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        product_id = uuid4()
        load.return_value = (recommendation(product_id), [])
        response = self.client.post(reverse("decisions:prepare", args=[product_id]), {"quantity": "85"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RestockDraft.objects.exists())


class _EmptyResult:
    def mappings(self):
        return self

    def __iter__(self):
        return iter(())

    def scalar_one(self):
        return 0

    def one_or_none(self):
        return None


class _RecordingSession:
    def __init__(self, company_id):
        self.info = {"company_id": company_id}
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return _EmptyResult()


class TenantRepositoryTests(SimpleTestCase):
    def test_decision_reads_always_receive_the_active_company(self):
        company_id = str(uuid4())
        db = _RecordingSession(company_id)
        repository = DecisionRepository(db)

        repository.get_latest_product_forecasts()
        repository.get_active_suppliers()
        repository.get_anomalies()
        repository.get_active_product_count()
        repository.get_forecasted_product_ids()

        self.assertTrue(db.calls)
        for sql, params in db.calls:
            self.assertIn("company_id", sql)
            self.assertEqual(params.get("company_id"), company_id)

    def test_product_reads_are_explicitly_tenant_scoped(self):
        company_id = str(uuid4())
        db = _RecordingSession(company_id)
        repository = ProductRepository(db)

        repository.get_all_active_products()
        with self.assertRaisesMessage(ValueError, "Produit introuvable"):
            repository.get_by_id(str(uuid4()))

        for sql, params in db.calls:
            self.assertIn("company_id", sql)
            self.assertEqual(params.get("company_id"), company_id)
