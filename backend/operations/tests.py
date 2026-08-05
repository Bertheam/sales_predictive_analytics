from datetime import date, time
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Membership
from .forms import CustomerForm, ProductForm, SupplierForm


class OperationAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="operations@example.com",
            password="A-secure-password-2026",
            full_name="Gestionnaire Test",
        )
        self.company = Company.objects.create(code="operations", name="Dépôt Opérations")
        self.membership = Membership.objects.create(
            user=self.user,
            company=self.company,
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()

    def test_operational_pages_render_for_selected_company(self):
        for route in (
            "operations:products", "operations:customers", "operations:suppliers",
            "operations:stocks", "operations:sales",
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Dépôt Opérations")

    def test_list_filters_have_visible_labels(self):
        expectations = {
            "operations:products": ("Recherche", "Catégorie", "Statut"),
            "operations:customers": ("Recherche", "Type de client", "Statut"),
            "operations:suppliers": ("Recherche", "Statut"),
            "operations:stocks": ("Recherche", "Niveau de stock"),
            "operations:sales": ("Recherche", "Du", "Au"),
        }
        for route, labels in expectations.items():
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                for label in labels:
                    self.assertContains(response, f">{label}</label>")

    def test_viewer_can_read_but_cannot_create_product(self):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        self.assertEqual(self.client.get(reverse("operations:products")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operations:product-create")).status_code, 403)

    @patch("operations.views.get_product", return_value=None)
    def test_foreign_or_unknown_product_is_not_exposed(self, _get_product):
        response = self.client.get(reverse("operations:product-edit", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    @patch("operations.views.sale_detail", return_value=(None, []))
    def test_foreign_or_unknown_sale_is_not_exposed(self, _sale_detail):
        response = self.client.get(reverse("operations:sale-detail", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    @patch("operations.views.receipt_detail", return_value=None)
    def test_foreign_or_unknown_receipt_is_not_exposed(self, _receipt_detail):
        response = self.client.get(
            reverse("operations:receipt-edit", args=[uuid4()])
        )
        self.assertEqual(response.status_code, 404)

    @patch("operations.views.get_customer", return_value=None)
    def test_foreign_or_unknown_customer_is_not_exposed(self, _get_customer):
        response = self.client.get(
            reverse("operations:customer-edit", args=[uuid4()])
        )
        self.assertEqual(response.status_code, 404)

    @patch("operations.views.get_supplier", return_value=None)
    def test_foreign_or_unknown_supplier_is_not_exposed(self, _get_supplier):
        response = self.client.get(
            reverse("operations:supplier-edit", args=[uuid4()])
        )
        self.assertEqual(response.status_code, 404)

    @patch("operations.views.set_product_archived")
    def test_product_is_archived_logically(self, archive):
        product_id = uuid4()
        archive.return_value = {"id": product_id, "code": "PRD-000001", "name": "Cola"}
        response = self.client.post(
            reverse("operations:product-archive", args=[product_id]),
            {"action": "archive"},
        )
        self.assertRedirects(response, reverse("operations:products"))
        archive.assert_called_once_with(
            self.company.id, product_id, archived=True, user_id=self.user.id
        )

    @patch("operations.views.set_customer_archived")
    def test_customer_is_archived_logically(self, archive):
        customer_id = uuid4()
        archive.return_value = {"id": customer_id, "code": "CLI-000001", "name": "Client Test"}
        response = self.client.post(
            reverse("operations:customer-archive", args=[customer_id]),
            {"action": "archive"},
        )
        self.assertRedirects(response, reverse("operations:customers"))
        archive.assert_called_once_with(
            self.company.id, customer_id, archived=True, user_id=self.user.id
        )

    @patch("operations.views.set_supplier_archived")
    def test_supplier_is_archived_logically(self, archive):
        supplier_id = uuid4()
        archive.return_value = {"id": supplier_id, "code": "FRS-000001", "name": "Fournisseur Test"}
        response = self.client.post(
            reverse("operations:supplier-archive", args=[supplier_id]),
            {"action": "archive"},
        )
        self.assertRedirects(response, reverse("operations:suppliers"))
        archive.assert_called_once_with(
            self.company.id, supplier_id, archived=True, user_id=self.user.id
        )

    def test_operational_creation_pages_are_available_to_admin(self):
        for route in (
            "operations:customer-create", "operations:supplier-create",
            "operations:sale-create", "operations:receipt-create",
            "operations:movement-create",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_viewer_cannot_create_stock_or_sale_operations(self):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        for route in (
            "operations:customer-create", "operations:supplier-create",
            "operations:sale-create", "operations:receipt-create",
            "operations:movement-create",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_viewer_cannot_modify_or_cancel_operations(self):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        identifiers = {
            "operations:sale-edit": uuid4(),
            "operations:sale-cancel": uuid4(),
            "operations:receipt-edit": uuid4(),
            "operations:receipt-cancel": uuid4(),
        }
        for route, identifier in identifiers.items():
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=[identifier]))
                self.assertEqual(response.status_code, 403)

    def test_product_code_is_not_an_editable_field(self):
        self.assertNotIn("code", ProductForm().fields)

    def test_business_codes_are_not_editable_fields(self):
        self.assertNotIn("code", CustomerForm().fields)
        self.assertNotIn("code", SupplierForm().fields)

    @patch("operations.views.sales_overview")
    def test_sales_are_sortable_paginated_and_localized(self, overview):
        rows = [
            {
                "id": uuid4(), "sale_number": f"VTE-{index:06d}",
                "sale_date": date(2026, 7, 14), "sale_time": time(12, 0),
                "customer_name": f"Client {index:02d}", "payment_status": "PAID",
                "total_amount": Decimal(index), "item_count": 1,
                "quantity": Decimal(1),
            }
            for index in range(1, 31)
        ]
        overview.return_value = (
            rows,
            {"revenue": 465, "count": 30, "quantity": 30, "average": 15.5},
            date(2026, 7, 14), date(2026, 7, 14),
        )

        response = self.client.get(reverse("operations:sales"), {
            "sort": "amount", "direction": "desc", "page": 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payée")
        self.assertContains(response, "Résultats <strong class=\"text-ink\">26–30</strong>", html=False)
        self.assertContains(response, "aria-sort=\"descending\"")
        self.assertContains(response, "VTE-000001")
        self.assertNotContains(response, "VTE-000030")
