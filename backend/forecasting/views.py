from django.contrib import messages
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.models import AuditLog
from audit.services import record_audit
from companies.models import Membership
from companies.permissions import company_required

from .forms import ForecastJobForm
from .data import get_company_freshness, get_product_freshness
from .models import ForecastJob, ProductModelChampion
from .tasks import generate_product_forecast


GENERATE_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ANALYST}


def _freshness_error(freshness):
    if not freshness["exists"]:
        return "Ce produit n’est pas disponible dans le dépôt actif."
    if freshness["last_sale_date"] is None:
        return "Aucune vente historique n’est disponible pour ce produit."
    if freshness["age_days"] > settings.FORECAST_MAX_DATA_AGE_DAYS:
        return (
            f"La dernière vente disponible date du "
            f"{freshness['last_sale_date']:%d/%m/%Y} "
            f"({freshness['age_days']} jours de retard). "
            "Importez ou saisissez les ventes manquantes avant de prévoir."
        )
    return ""


def _enqueue(job):
    async_result = generate_product_forecast.delay(str(job.id))
    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id"])
    return async_result


@company_required
def forecast_jobs(request):
    can_generate = request.membership.role in GENERATE_ROLES
    form = ForecastJobForm(request.POST or None, company_id=request.company.id)

    if request.method == "POST":
        if not can_generate:
            return HttpResponseForbidden(
                "Votre rôle ne permet pas de générer une prévision."
            )
        if form.is_valid():
            product_id = form.cleaned_data["product_id"]
            product_name = dict(form.fields["product_id"].choices)[product_id]
            freshness = get_product_freshness(request.company.id, product_id)
            freshness_error = _freshness_error(freshness)
            if freshness_error:
                form.add_error("product_id", freshness_error)
            else:
                try:
                    with transaction.atomic():
                        job = ForecastJob.objects.create(
                            company=request.company,
                            product_id=product_id,
                            product_name=product_name,
                            requested_by=request.user,
                            horizon=form.cleaned_data["horizon"],
                        )
                except IntegrityError:
                    form.add_error(
                        "product_id",
                        "Une prévision est déjà en attente ou en cours pour ce produit.",
                    )
                else:
                    try:
                        async_result = _enqueue(job)
                    except Exception as exc:
                        job.status = ForecastJob.Status.FAILED
                        job.error_message = f"La file de traitements est indisponible : {exc}"[:2000]
                        job.save(update_fields=["status", "error_message"])
                        messages.error(request, "Le moteur de traitements est indisponible. Réessayez dans quelques instants.")
                        return redirect("forecasting:jobs")
                    record_audit(
                        request,
                        action=AuditLog.Action.FORECAST,
                        resource_type="forecast_job",
                        resource_id=job.id,
                        description=f"Génération de prévision demandée pour {product_name}.",
                        metadata={"horizon": job.horizon, "celery_task_id": async_result.id},
                    )
                    messages.success(request, "La prévision a été placée dans la file de traitements.")
                    return redirect("forecasting:jobs")

    jobs = ForecastJob.objects.filter(company=request.company).select_related(
        "requested_by"
    )[:50]
    has_active_jobs = any(
        job.status in {ForecastJob.Status.QUEUED, ForecastJob.Status.RUNNING}
        for job in jobs
    )
    company_freshness = get_company_freshness(request.company.id)
    champions = list(
        ProductModelChampion.objects.filter(company=request.company).order_by(
            "-last_evaluated_at"
        )[:12]
    )
    stable_models = sum(
        champion.last_decision == ProductModelChampion.Decision.RETAINED
        for champion in champions
    )
    return render(request, "forecasting/jobs.html", {
        "form": form,
        "jobs": jobs,
        "can_generate": can_generate,
        "has_active_jobs": has_active_jobs,
        "freshness": company_freshness,
        "freshness_is_stale": (
            company_freshness["age_days"] is not None
            and company_freshness["age_days"] > settings.FORECAST_MAX_DATA_AGE_DAYS
        ),
        "max_data_age_days": settings.FORECAST_MAX_DATA_AGE_DAYS,
        "champions": champions,
        "stable_models": stable_models,
        "replacement_threshold": settings.FORECAST_CHAMPION_MIN_IMPROVEMENT,
    })


@require_POST
@company_required
def retry_forecast_job(request, job_id):
    if request.membership.role not in GENERATE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas de relancer une prévision."
        )
    job = get_object_or_404(ForecastJob, pk=job_id, company=request.company)
    if job.status != ForecastJob.Status.FAILED:
        messages.warning(request, "Seule une prévision en échec peut être relancée.")
        return redirect("forecasting:jobs")

    freshness_error = _freshness_error(
        get_product_freshness(request.company.id, job.product_id)
    )
    if freshness_error:
        messages.error(request, freshness_error)
        return redirect("forecasting:jobs")

    job.status = ForecastJob.Status.QUEUED
    job.requested_by = request.user
    job.celery_task_id = ""
    job.error_message = ""
    job.started_at = None
    job.completed_at = None
    try:
        with transaction.atomic():
            job.save(update_fields=[
                "status", "requested_by", "celery_task_id", "error_message",
                "started_at", "completed_at",
            ])
    except IntegrityError:
        messages.warning(
            request, "Une autre prévision est déjà active pour ce produit."
        )
        return redirect("forecasting:jobs")
    try:
        async_result = _enqueue(job)
    except Exception as exc:
        job.status = ForecastJob.Status.FAILED
        job.error_message = f"La file de traitements est indisponible : {exc}"[:2000]
        job.save(update_fields=["status", "error_message"])
        messages.error(request, "La relance n’a pas pu être envoyée au moteur.")
        return redirect("forecasting:jobs")

    record_audit(
        request,
        action=AuditLog.Action.FORECAST,
        resource_type="forecast_job",
        resource_id=job.id,
        description=f"Prévision relancée pour {job.product_name}.",
        metadata={"celery_task_id": async_result.id},
    )
    messages.success(request, "La prévision a été replacée dans la file.")
    return redirect("forecasting:jobs")
