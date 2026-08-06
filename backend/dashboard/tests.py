from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from companies.models import Company, Membership
from .data import percentage_change


class PercentageChangeTests(TestCase):
    def test_handles_integer_counts_and_decimal_values(self):
        self.assertEqual(percentage_change(12, 10), Decimal("20.0"))
        self.assertEqual(percentage_change(Decimal("90"), Decimal("100")), Decimal("-10.0"))

    def test_handles_empty_comparison_without_division_by_zero(self):
        self.assertEqual(percentage_change(0, 0), Decimal("0"))
        self.assertIsNone(percentage_change(10, 0))


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="secret", full_name="Propriétaire"
        )
        self.company = Company.objects.create(code="depot-test", name="Dépôt test")
        Membership.objects.create(
            company=self.company, user=self.user, role=Membership.Role.OWNER
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

    @patch("dashboard.views.get_overview_snapshot")
    def test_overview_uses_real_snapshot_and_hides_new_workspace(self, service):
        service.return_value = {
            "company_configured": True,
            "start_date": date(2026, 7, 31), "end_date": date(2026, 8, 6),
            "previous_start": date(2026, 7, 24), "previous_end": date(2026, 7, 30),
            "last_updated_at": None, "active_products": 2,
            "revenue": Decimal("1000"), "sales_count": 2,
            "quantity_sold": Decimal("3"), "current_stock": Decimal("20"),
            "risk_products": 1, "revenue_change": Decimal("10"),
            "sales_change": Decimal("0"), "quantity_change": None,
            "stock_change": Decimal("-5"),
            "setup_steps": [
                {"label": "Dépôt configuré", "complete": True, "url_name": "companies:edit"},
                {"label": "Produits ou stocks ajoutés", "complete": True, "url_name": "operations:products"},
                {"label": "Premières ventes enregistrées", "complete": True, "url_name": "operations:sales"},
            ],
            "setup_completed": 3, "setup_percent": 100,
        }
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3 / 3")
        self.assertNotContains(response, "NOUVEL ESPACE")
        self.assertContains(response, reverse("operations:sales"))

    @patch("dashboard.views.get_activity_dashboard")
    def test_activity_defaults_to_thirty_days(self, service):
        service.return_value = self._activity_data()
        with patch("dashboard.views.timezone.localdate", return_value=date(2026, 8, 6)):
            response = self.client.get(reverse("dashboard:activity"))
        self.assertEqual(response.status_code, 200)
        service.assert_called_once_with(self.company.id, date(2026, 7, 8), date(2026, 8, 6))
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "Meilleurs produits")

    def _activity_data(self):
        return {
            "start_date": date(2026, 7, 8), "end_date": date(2026, 8, 6),
            "previous_start": date(2026, 6, 8), "previous_end": date(2026, 7, 7),
            "last_updated_at": None, "has_sales": False,
            "metrics": [
                {"key": "revenue", "label": "Chiffre d’affaires", "value": Decimal("0"), "change": Decimal("0")},
                {"key": "quantity", "label": "Quantité vendue", "value": Decimal("0"), "change": Decimal("0")},
                {"key": "transactions", "label": "Transactions", "value": 0, "change": Decimal("0")},
                {"key": "average_basket", "label": "Panier moyen", "value": Decimal("0"), "change": Decimal("0")},
            ],
            "chart": {"has_data": False, "revenue_points": "", "quantity_points": ""},
            "top_products": [], "top_categories": [], "top_customers": [],
            "payment_methods": [], "payment_statuses": [], "weekdays": [],
        }
