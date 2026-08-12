from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Membership
from app.repositories.decision_repository import DecisionRepository
from app.repositories.product_repository import ProductRepository

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderReceipt,
    RestockDraft,
)


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
        self.assertContains(response, "1 produit à commander")
        self.assertContains(response, "85 colis")
        self.assertContains(response, 'aria-label="Filtres des recommandations"')
        self.assertNotContains(response, '<details class="filter-drawer"')

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


class ProcurementWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner-procurement@example.com",
            password="A-secure-password-2026",
        )
        self.company = Company.objects.create(
            code="procurement-depot", name="Dépôt Approvisionnement"
        )
        self.membership = Membership.objects.create(
            user=self.user,
            company=self.company,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()
        self.supplier_id = uuid4()

    def create_draft(self, *, product_name="Cola 50 cl", supplier_id=None):
        return RestockDraft.objects.create(
            company=self.company,
            product_id=uuid4(),
            product_name=product_name,
            supplier_id=supplier_id if supplier_id is not None else self.supplier_id,
            supplier_name="Grossiste Test",
            quantity=Decimal("12.00"),
            created_by=self.user,
        )

    def create_order(self, *, quantity="10.00", company=None):
        company = company or self.company
        order = PurchaseOrder.objects.create(
            company=company,
            order_number=PurchaseOrder.new_number(),
            supplier_id=self.supplier_id,
            supplier_name="Grossiste Test",
            created_by=self.user,
            updated_by=self.user,
        )
        item = PurchaseOrderItem.objects.create(
            order=order,
            product_id=uuid4(),
            product_code="PRD-001",
            product_name="Cola 50 cl",
            quantity_ordered=Decimal(quantity),
            unit_cost=Decimal("4500.00"),
        )
        return order, item

    def test_approvisionnement_has_one_clear_three_step_navigation(self):
        response = self.client.get(reverse("decisions:orders"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommandations")
        self.assertContains(response, "Commandes")
        self.assertContains(response, "Réceptions")
        self.assertContains(response, "Nouvelle commande")
        self.assertContains(response, f'href="{reverse("decisions:orders")}"')

    @patch("decisions.views.operational_references")
    def test_owner_can_create_an_order_without_recommendation(self, references):
        first_product = uuid4()
        second_product = uuid4()
        references.return_value = {
            "customers": [],
            "suppliers": [
                {
                    "id": self.supplier_id,
                    "code": "FRS-001",
                    "name": "Grossiste Libre",
                }
            ],
            "products": [
                {
                    "id": first_product,
                    "code": "PRD-010",
                    "name": "Bissap 33 cl",
                    "purchase_price": Decimal("2500.00"),
                },
                {
                    "id": second_product,
                    "code": "PRD-011",
                    "name": "Gingembre 33 cl",
                    "purchase_price": Decimal("2800.00"),
                },
            ],
        }

        response = self.client.post(
            reverse("decisions:manual-order-create"),
            {
                "supplier_id": str(self.supplier_id),
                "notes": "Commande décidée par le gérant.",
                "items-TOTAL_FORMS": "2",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "1",
                "items-MAX_NUM_FORMS": "20",
                "items-0-product_id": str(first_product),
                "items-0-quantity_ordered": "15",
                "items-1-product_id": str(second_product),
                "items-1-quantity_ordered": "8",
            },
        )

        order = PurchaseOrder.objects.get()
        self.assertRedirects(
            response,
            reverse("decisions:order-detail", args=[order.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.items.count(), 2)
        self.assertFalse(RestockDraft.objects.exists())
        self.assertTrue(
            order.company.audit_logs.filter(
                resource_type="purchase_order", metadata__source="manual"
            ).exists()
        )

    @patch("decisions.views.operational_references")
    def test_manual_order_form_starts_with_one_dynamic_product_line(self, references):
        references.return_value = {"customers": [], "suppliers": [], "products": []}

        response = self.client.get(reverse("decisions:manual-order-create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["items"].total_form_count(), 1)
        self.assertContains(response, "Ajouter un produit")
        self.assertContains(response, "même sans recommandation")
        self.assertContains(response, "data-remove-form-row")
        self.assertContains(response, "business-form--line-items")
        self.assertContains(response, "line-form manual-order-line")

    @patch("decisions.views.operational_references")
    def test_owner_creates_one_supplier_order_from_prepared_plans(self, references):
        first = self.create_draft(product_name="Cola 50 cl")
        second = self.create_draft(product_name="Eau 1,5 L")
        references.return_value = {
            "products": [
                {
                    "id": first.product_id,
                    "code": "PRD-001",
                    "purchase_price": Decimal("4500.00"),
                },
                {
                    "id": second.product_id,
                    "code": "PRD-002",
                    "purchase_price": Decimal("3000.00"),
                },
            ],
            "suppliers": [
                {
                    "id": self.supplier_id,
                    "code": "FRS-001",
                    "name": "Grossiste Test",
                }
            ],
        }

        response = self.client.post(
            reverse("decisions:create-order"),
            {
                "draft_ids": [str(first.id), str(second.id)],
                "notes": "Livrer le matin.",
            },
        )

        order = PurchaseOrder.objects.get()
        self.assertRedirects(
            response,
            reverse("decisions:order-detail", args=[order.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.notes, "Livrer le matin.")
        self.assertEqual(
            set(
                RestockDraft.objects.filter(id__in=[first.id, second.id]).values_list(
                    "status", flat=True
                )
            ),
            {RestockDraft.Status.APPROVED},
        )
        self.assertTrue(
            order.company.audit_logs.filter(resource_type="purchase_order").exists()
        )

    @patch("decisions.views.operational_references")
    def test_order_cannot_mix_suppliers(self, references):
        first = self.create_draft()
        second = self.create_draft(supplier_id=uuid4())
        references.return_value = {"products": [], "suppliers": []}

        response = self.client.post(
            reverse("decisions:create-order"),
            {"draft_ids": [str(first.id), str(second.id)]},
        )

        self.assertRedirects(
            response, reverse("decisions:orders"), fetch_redirect_response=False
        )
        self.assertFalse(PurchaseOrder.objects.exists())

    def test_order_can_be_marked_as_sent(self):
        order, _ = self.create_order()

        response = self.client.post(
            reverse("decisions:send-order", args=[order.id])
        )

        self.assertRedirects(
            response,
            reverse("decisions:order-detail", args=[order.id]),
            fetch_redirect_response=False,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.SENT)
        self.assertIsNotNone(order.sent_at)

    @patch("decisions.views.create_receipt")
    def test_partial_then_complete_receipt_updates_order_without_duplicate_stock_logic(
        self, create_receipt
    ):
        order, item = self.create_order(quantity="10.00")
        create_receipt.side_effect = [
            {"id": uuid4(), "number": "REC-001"},
            {"id": uuid4(), "number": "REC-002"},
        ]
        url = reverse("decisions:receive-order", args=[order.id])

        response = self.client.post(
            url,
            {
                "receipt_date": date.today().isoformat(),
                f"quantity_{item.id}": "4.00",
                f"unit_cost_{item.id}": "4500.00",
            },
        )

        self.assertRedirects(
            response,
            reverse("decisions:order-detail", args=[order.id]),
            fetch_redirect_response=False,
        )
        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.quantity_received, Decimal("4.00"))
        self.assertEqual(order.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertEqual(PurchaseOrderReceipt.objects.count(), 1)

        response = self.client.post(
            url,
            {
                "receipt_date": date.today().isoformat(),
                f"quantity_{item.id}": "6.00",
                f"unit_cost_{item.id}": "4600.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.quantity_received, Decimal("10.00"))
        self.assertEqual(item.unit_cost, Decimal("4600.00"))
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIVED)
        self.assertIsNotNone(order.received_at)
        self.assertEqual(PurchaseOrderReceipt.objects.count(), 2)
        self.assertEqual(create_receipt.call_count, 2)

    def test_viewer_cannot_create_or_receive_an_order(self):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        draft = self.create_draft()
        order, _ = self.create_order()

        create_response = self.client.post(
            reverse("decisions:create-order"), {"draft_ids": [str(draft.id)]}
        )
        receive_response = self.client.post(
            reverse("decisions:receive-order", args=[order.id])
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(receive_response.status_code, 403)

    def test_order_detail_is_strictly_tenant_scoped(self):
        other_company = Company.objects.create(
            code="another-procurement-depot", name="Autre dépôt"
        )
        order, _ = self.create_order(company=other_company)

        response = self.client.get(
            reverse("decisions:order-detail", args=[order.id])
        )

        self.assertEqual(response.status_code, 404)


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
        with self.assertRaisesMessage(ValueError, "Produit introuvable"):
            repository.get_stock_snapshot(str(uuid4()))

        for sql, params in db.calls:
            self.assertIn("company_id", sql)
            self.assertEqual(params.get("company_id"), company_id)
