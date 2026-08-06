from unittest.mock import patch
from uuid import uuid4
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import TestCase
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Membership

from .models import ForecastJob, ProductModelChampion
from .services import decide_champion
from .tasks import run_daily_ml_maintenance


class ForecastInfrastructureTests(SimpleTestCase):
    @override_settings(CELERY_AUTOMATION_ENABLED=False)
    def test_periodic_maintenance_is_safe_by_default(self):
        result = run_daily_ml_maintenance.run()
        self.assertEqual(result, {"status": "disabled", "processed_companies": 0})

    def test_background_session_requires_an_explicit_company(self):
        from app.database.session import session_for_company

        company_id = uuid4()
        session = session_for_company(company_id)
        try:
            self.assertEqual(session.info["company_id"], str(company_id))
        finally:
            session.close()

    def _evaluation(self, champion_mae=10, challenger_mae=9.6):
        rows = [
            {"model": "challenger", "label": "Challenger", "mae": challenger_mae, "rmse": 11, "mape": 20},
            {"model": "champion", "label": "Champion", "mae": champion_mae, "rmse": 12, "mape": 22},
        ]
        return {
            "ranking": sorted(rows, key=lambda row: row["mae"]),
            "models": {
                row["model"]: {"mae": row["mae"], "rmse": row["rmse"], "mape": row["mape"], "wape": 25, "bias": 1}
                for row in rows
            },
        }

    def test_first_evaluation_installs_best_model(self):
        decision = decide_champion(None, self._evaluation(), 5)
        self.assertEqual(decision.model_key, "challenger")
        self.assertEqual(decision.decision, ProductModelChampion.Decision.INSTALLED)

    def test_small_gain_keeps_current_champion(self):
        current = SimpleNamespace(model_key="champion")
        decision = decide_champion(current, self._evaluation(10, 9.6), 5)
        self.assertEqual(decision.model_key, "champion")
        self.assertEqual(decision.decision, ProductModelChampion.Decision.RETAINED)

    def test_clear_gain_replaces_current_champion(self):
        current = SimpleNamespace(model_key="champion")
        decision = decide_champion(current, self._evaluation(10, 9), 5)
        self.assertEqual(decision.model_key, "challenger")
        self.assertEqual(decision.decision, ProductModelChampion.Decision.REPLACED)


class ForecastJobPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="analyste@example.com", password="A-secure-password-2026"
        )
        self.company = Company.objects.create(code="forecast-test", name="Dépôt Prévision")
        self.membership = Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.ANALYST
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()
        freshness_patcher = patch(
            "forecasting.views.get_company_freshness",
            return_value={"last_sale_date": date.today(), "age_days": 0},
        )
        freshness_patcher.start()
        self.addCleanup(freshness_patcher.stop)

    @patch("forecasting.forms.product_choices", return_value=[])
    def test_page_is_available(self, _choices):
        response = self.client.get(reverse("forecasting:jobs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prévisions de ventes")
        self.assertContains(response, "Préparez vos stocks")
        self.assertContains(response, "Aucun réglage complexe")

    @patch("forecasting.forms.product_choices", return_value=[])
    def test_technical_metrics_are_hidden_in_details(self, _choices):
        ProductModelChampion.objects.create(
            company=self.company,
            product_id=uuid4(),
            product_name="Cola 50 cl",
            model_key="moving_average_7",
            model_label="Moyenne mobile 7 jours",
            mae=8.62,
            wape=18.4,
        )
        response = self.client.get(reverse("forecasting:jobs"))
        self.assertContains(response, "Voir les détails techniques")
        self.assertContains(response, "Erreur moyenne")

    @patch("forecasting.forms.product_choices", return_value=[])
    def test_successful_job_links_to_readable_result(self, _choices):
        job = ForecastJob.objects.create(
            company=self.company,
            product_id=uuid4(),
            product_name="Cola 50 cl",
            status=ForecastJob.Status.SUCCESS,
            forecast_id=uuid4(),
            model_name="Moyenne mobile 7 jours",
        )
        response = self.client.get(reverse("forecasting:jobs"))
        self.assertContains(response, "Voir le résultat")
        self.assertContains(response, reverse("forecasting:result", args=[job.id]))

    @patch("forecasting.views.FutureForecastService")
    @patch("forecasting.views.session_for_company")
    def test_result_page_exposes_daily_business_values(self, session_factory, service_class):
        product_id = uuid4()
        job = ForecastJob.objects.create(
            company=self.company,
            product_id=product_id,
            product_name="Cola 50 cl",
            status=ForecastJob.Status.SUCCESS,
            forecast_id=uuid4(),
            forecast_number="FC-TEST-001",
            model_name="Régression linéaire",
            result={"mae": 4.2, "rmse": 5.1, "mape": 12.0, "wape": 10.0, "bias": 0.3},
        )
        session_factory.return_value.__enter__.return_value = MagicMock()
        service_class.return_value.get_forecast_results.return_value = [{
            "forecast_date": date.today() + timedelta(days=1),
            "predicted_quantity": 12,
            "predicted_p50": 12,
            "predicted_p80": 14,
            "predicted_p90": 16,
            "lower_bound": 9,
            "upper_bound": 17,
            "predicted_revenue": 102000,
            "recommended_stock": 7,
            "actual_quantity": None,
            "absolute_error": None,
        }]

        response = self.client.get(reverse("forecasting:result", args=[job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demande prévue par jour")
        self.assertContains(response, "Scénario prudent")
        self.assertContains(response, "102000")
        service_class.return_value.get_forecast_results.assert_called_once_with(
            str(job.forecast_id)
        )

    def test_result_of_another_company_is_not_accessible(self):
        foreign_company = Company.objects.create(code="other-forecast", name="Autre dépôt")
        job = ForecastJob.objects.create(
            company=foreign_company,
            product_id=uuid4(),
            product_name="Produit privé",
            status=ForecastJob.Status.SUCCESS,
            forecast_id=uuid4(),
        )
        response = self.client.get(reverse("forecasting:result", args=[job.id]))
        self.assertEqual(response.status_code, 404)

    @patch("forecasting.views.generate_product_forecast.delay")
    @patch("forecasting.views.get_product_freshness")
    @patch("forecasting.forms.product_choices")
    def test_analyst_can_queue_a_company_scoped_job(self, choices, freshness, delay):
        product_id = uuid4()
        choices.return_value = [(str(product_id), "Cola 50 cl · PRD-001")]
        freshness.return_value = {
            "exists": True, "last_sale_date": date.today(), "age_days": 0
        }
        delay.return_value.id = "celery-task-1"
        response = self.client.post(reverse("forecasting:jobs"), {
            "product_id": str(product_id), "horizon": "7"
        })
        self.assertRedirects(
            response, reverse("forecasting:jobs"), fetch_redirect_response=False
        )
        job = ForecastJob.objects.get()
        self.assertEqual(job.company, self.company)
        self.assertEqual(job.celery_task_id, "celery-task-1")
        delay.assert_called_once_with(str(job.id))

    @patch("forecasting.views.generate_product_forecast.delay")
    @patch("forecasting.views.get_product_freshness")
    @patch("forecasting.forms.product_choices")
    def test_stale_product_is_rejected(self, choices, freshness, delay):
        product_id = uuid4()
        choices.return_value = [(str(product_id), "Cola 50 cl · PRD-001")]
        freshness.return_value = {
            "exists": True,
            "last_sale_date": date.today() - timedelta(days=4),
            "age_days": 4,
        }
        response = self.client.post(reverse("forecasting:jobs"), {
            "product_id": str(product_id), "horizon": "7"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "4 jours de retard")
        self.assertFalse(ForecastJob.objects.exists())
        delay.assert_not_called()

    @patch("forecasting.views.generate_product_forecast.delay")
    @patch("forecasting.views.get_product_freshness")
    @patch("forecasting.forms.product_choices")
    def test_active_product_job_cannot_be_duplicated(self, choices, freshness, delay):
        product_id = uuid4()
        choices.return_value = [(str(product_id), "Cola 50 cl · PRD-001")]
        freshness.return_value = {
            "exists": True, "last_sale_date": date.today(), "age_days": 0
        }
        ForecastJob.objects.create(
            company=self.company,
            product_id=product_id,
            product_name="Cola 50 cl · PRD-001",
            status=ForecastJob.Status.RUNNING,
        )
        response = self.client.post(reverse("forecasting:jobs"), {
            "product_id": str(product_id), "horizon": "7"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "déjà en attente ou en cours")
        self.assertEqual(ForecastJob.objects.count(), 1)
        delay.assert_not_called()

    @patch("forecasting.views.generate_product_forecast.delay")
    @patch("forecasting.views.get_product_freshness")
    def test_failed_job_can_be_retried(self, freshness, delay):
        product_id = uuid4()
        freshness.return_value = {
            "exists": True, "last_sale_date": date.today(), "age_days": 0
        }
        delay.return_value.id = "retry-task-1"
        job = ForecastJob.objects.create(
            company=self.company,
            product_id=product_id,
            product_name="Cola 50 cl",
            status=ForecastJob.Status.FAILED,
            error_message="Erreur temporaire",
        )
        response = self.client.post(reverse("forecasting:retry", args=[job.id]))
        self.assertRedirects(
            response, reverse("forecasting:jobs"), fetch_redirect_response=False
        )
        job.refresh_from_db()
        self.assertEqual(job.status, ForecastJob.Status.QUEUED)
        self.assertEqual(job.celery_task_id, "retry-task-1")
        self.assertEqual(job.error_message, "")

    @patch("forecasting.forms.product_choices", return_value=[])
    def test_viewer_cannot_queue_a_job(self, _choices):
        self.membership.role = Membership.Role.VIEWER
        self.membership.save(update_fields=["role"])
        response = self.client.post(reverse("forecasting:jobs"))
        self.assertEqual(response.status_code, 403)
