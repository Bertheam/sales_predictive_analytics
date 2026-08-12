from datetime import date, time
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from companies.models import Company, Membership
from .forms import CustomerForm, ProductForm, SupplierForm
from .models import PendingDataImport


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

    @patch("operations.views.sale_detail")
    def test_sale_detail_translates_payment_method(self, sale_detail_mock):
        sale_id = uuid4()
        sale_detail_mock.return_value = ({
            "id": sale_id,
            "sale_number": "VTE-TEST",
            "customer_name": "Client test",
            "sale_date": date.today(),
            "sale_time": time(10, 0),
            "salesperson_name": "Gestionnaire Test",
            "payment_method": "CASH",
            "payment_status": "PAID",
            "subtotal": Decimal("10000"),
            "discount_amount": Decimal("0"),
            "total_amount": Decimal("10000"),
        }, [])

        response = self.client.get(
            reverse("operations:sale-detail", args=[sale_id])
        )

        self.assertContains(response, "Espèces")
        self.assertNotContains(response, ">CASH<")

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

    def test_new_sale_starts_with_one_line_and_an_add_product_button(self):
        response = self.client.get(reverse("operations:sale-create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["items"].total_form_count(), 1)
        self.assertContains(response, "Ajouter un produit")
        self.assertContains(response, "data-dynamic-formset")
        self.assertContains(response, "data-remove-form-row")

    def test_new_receipt_starts_with_one_dynamic_product_line(self):
        response = self.client.get(reverse("operations:receipt-create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["items"].total_form_count(), 1)
        self.assertContains(response, "Ajouter un produit")
        self.assertContains(response, "data-dynamic-formset")
        self.assertContains(response, "data-remove-form-row")

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


class DataImportWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="import@example.com",
            password="A-secure-password-2026",
            full_name="Responsable Import",
        )
        self.company = Company.objects.create(code="import", name="Dépôt Import")
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

    @staticmethod
    def _analysis():
        return {
            "file_name": "ventes.xlsx",
            "file_type": "XLSX",
            "file_hash": "a" * 64,
            "import_type": "SALES",
            "total_rows": 2,
            "valid_rows": [{"sale_reference": "FACT-1"}],
            "invalid_rows": [
                {"_row_number": 3, "_errors": ["Produit inconnu"]}
            ],
            "duplicate_rows": [],
            "preview": pd.DataFrame(
                [
                    {"Ligne": 2, "Statut": "Valide", "sale_reference": "FACT-1"},
                    {"Ligne": 3, "Statut": "Invalide", "sale_reference": "FACT-2"},
                ]
            ),
            "already_imported": False,
        }

    @patch("operations.views.DataImportService")
    @patch("operations.views.session_for_company")
    def test_import_page_uses_a_guided_modal_and_keeps_history_visible(self, session, service):
        session.return_value.__enter__.return_value = object()
        service.return_value.get_history.return_value = []

        response = self.client.get(reverse("operations:data-import"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historique des imports")
        self.assertContains(response, "Nouvel import")
        self.assertContains(response, "Assistant d’import")
        self.assertContains(response, 'data-import-wizard')
        self.assertContains(response, "Vérifier le fichier")
        self.assertContains(response, 'href="/import-excel/"')

    @patch("operations.views.DataImportService")
    @patch("operations.views.session_for_company")
    def test_template_download_returns_xlsx(self, session, service):
        session.return_value.__enter__.return_value = object()
        service.return_value.get_template.return_value = b"xlsx-content"

        response = self.client.get(
            reverse("operations:data-import-template", args=["SALES"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"xlsx-content")
        self.assertIn("modele_ventes.xlsx", response["Content-Disposition"])
        service.return_value.get_template.assert_called_once_with("SALES", "XLSX")

    @patch("operations.views.DataImportService")
    @patch("operations.views.session_for_company")
    def test_upload_is_analyzed_before_any_import(self, session, service):
        session.return_value.__enter__.return_value = object()
        service.return_value.get_history.return_value = []
        service.return_value.analyze_file.return_value = self._analysis()
        upload = SimpleUploadedFile(
            "ventes.xlsx",
            b"temporary-excel-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            reverse("operations:data-import"),
            {"import_type": "SALES", "excel_file": upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vérification terminée")
        self.assertContains(response, "Ajouter uniquement les lignes prêtes")
        self.assertEqual(PendingDataImport.objects.count(), 1)
        service.return_value.execute_import.assert_not_called()

    @patch("operations.views.DataImportService")
    @patch("operations.views.session_for_company")
    def test_confirmation_executes_import_and_writes_audit_log(self, session, service):
        session.return_value.__enter__.return_value = object()
        pending = PendingDataImport.objects.create(
            company=self.company,
            created_by=self.user,
            import_type="SALES",
            original_name="ventes.xlsx",
            content=b"temporary-excel-content",
            file_hash="a" * 64,
        )
        analysis = self._analysis()
        service.return_value.analyze_file.return_value = analysis
        service.return_value.execute_import.return_value = {
            "batch_id": uuid4(),
            "batch_number": "IMP-20260809-TEST",
            "imported_rows": 1,
            "invalid_rows": 1,
            "duplicate_rows": 0,
        }

        response = self.client.post(
            reverse("operations:data-import-confirm", args=[pending.id]),
            {"import_valid_only": "1"},
        )

        self.assertRedirects(response, reverse("operations:data-import"))
        self.assertFalse(PendingDataImport.objects.filter(id=pending.id).exists())
        service.return_value.execute_import.assert_called_once_with(
            analysis, import_valid_only=True
        )
        self.assertTrue(
            AuditLog.objects.filter(
                company=self.company,
                actor=self.user,
                action=AuditLog.Action.IMPORT,
            ).exists()
        )

    @patch("operations.views.DataImportService")
    @patch("operations.views.session_for_company")
    def test_viewer_cannot_access_import_workflow(self, session, service):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        response = self.client.get(reverse("operations:data-import"))
        self.assertEqual(response.status_code, 403)
        session.assert_not_called()
