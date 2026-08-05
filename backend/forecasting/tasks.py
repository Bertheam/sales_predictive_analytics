import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from app.database.session import session_for_company
from app.services.future_forecast_service import FutureForecastService
from app.services.ml_quality_service import MLQualityService
from audit.models import AuditLog
from audit.services import record_audit
from companies.models import Company

from .models import ForecastJob, ProductModelChampion
from .services import decide_champion, persist_champion


logger = logging.getLogger(__name__)


@shared_task(bind=True, name="forecasting.tasks.generate_product_forecast")
def generate_product_forecast(self, job_id):
    job = ForecastJob.objects.select_related("company", "requested_by").get(pk=job_id)
    if job.status == ForecastJob.Status.SUCCESS:
        return job.result

    job.status = ForecastJob.Status.RUNNING
    job.started_at = timezone.now()
    job.celery_task_id = self.request.id or job.celery_task_id
    job.error_message = ""
    job.save(update_fields=["status", "started_at", "celery_task_id", "error_message"])

    try:
        with session_for_company(job.company_id) as db:
            service = FutureForecastService(db)
            evaluation = service.forecast_service.evaluate_product(
                str(job.product_id), job.test_days
            )
            current = ProductModelChampion.objects.filter(
                company=job.company, product_id=job.product_id
            ).first()
            champion_decision = decide_champion(
                current,
                evaluation,
                settings.FORECAST_CHAMPION_MIN_IMPROVEMENT,
            )
            forecast = service.generate_and_save(
                str(job.product_id),
                horizon=job.horizon,
                test_days=job.test_days,
                evaluation=evaluation,
                selected_model=champion_decision.model_key,
            )
        champion = persist_champion(
            company=job.company,
            product_id=job.product_id,
            product_name=job.product_name,
            decision=champion_decision,
        )
        result = {
            "forecast_id": forecast["forecast_id"],
            "forecast_number": forecast["forecast_number"],
            "model": forecast["best_model_label"],
            "mae": round(float(forecast["metrics"]["mae"]), 4),
            "rmse": round(float(forecast["metrics"]["rmse"]), 4),
            "mape": round(float(forecast["metrics"]["mape"]), 4),
            "wape": round(float(forecast["metrics"]["wape"]), 4),
            "bias": round(float(forecast["metrics"]["bias"]), 4),
            "model_decision": champion.last_decision,
            "model_decision_label": champion.get_last_decision_display(),
            "decision_reason": champion.decision_reason,
            "challenger": champion.challenger_label,
            "improvement_percentage": champion.improvement_percentage,
        }
        job.status = ForecastJob.Status.SUCCESS
        job.model_name = result["model"]
        job.forecast_id = result["forecast_id"]
        job.forecast_number = result["forecast_number"]
        job.result = result
        job.completed_at = timezone.now()
        job.save(update_fields=[
            "status", "model_name", "forecast_id", "forecast_number",
            "result", "completed_at",
        ])
        record_audit(
            None,
            action=AuditLog.Action.FORECAST,
            resource_type="forecast",
            resource_id=result["forecast_id"],
            description=f"Prévision {result['forecast_number']} générée pour {job.product_name}.",
            company=job.company,
            actor=job.requested_by,
            metadata={"job_id": str(job.id), "model": result["model"]},
        )
        return result
    except Exception as exc:
        logger.exception("Échec de la prévision %s", job.id)
        job.status = ForecastJob.Status.FAILED
        job.error_message = str(exc)[:2000]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        raise


@shared_task(name="forecasting.tasks.run_daily_ml_maintenance")
def run_daily_ml_maintenance():
    if not settings.CELERY_AUTOMATION_ENABLED:
        return {"status": "disabled", "processed_companies": 0}

    processed = 0
    errors = []
    for company_id in Company.objects.filter(status=Company.Status.ACTIVE).values_list(
        "id", flat=True
    ):
        try:
            with session_for_company(company_id) as db:
                MLQualityService(db).get_dashboard_data()
            processed += 1
        except Exception as exc:
            logger.exception("Maintenance ML impossible pour le dépôt %s", company_id)
            errors.append({"company_id": str(company_id), "error": str(exc)[:500]})
    return {"status": "completed", "processed_companies": processed, "errors": errors}
