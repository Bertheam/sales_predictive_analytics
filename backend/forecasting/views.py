from math import sqrt

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
from app.database.session import session_for_company
from app.services.future_forecast_service import FutureForecastService

from .forms import ForecastJobForm
from .data import get_product_freshness, get_products_freshness
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


def _freshness_presentation(freshness):
    if not freshness or not freshness.get("exists"):
        return {
            "state": "missing",
            "title": "Choisissez un produit",
            "description": "Sa dernière vente sera vérifiée avant le calcul.",
            "action_label": "Voir les ventes",
        }
    last_sale_date = freshness.get("last_sale_date")
    if last_sale_date is None:
        return {
            "state": "missing",
            "title": "Aucune vente pour ce produit",
            "description": "Enregistrez quelques ventes avant de préparer une prévision.",
            "action_label": "Ajouter des ventes",
        }
    date_label = last_sale_date.strftime("%d/%m/%Y")
    if freshness["age_days"] > settings.FORECAST_MAX_DATA_AGE_DAYS:
        return {
            "state": "stale",
            "title": "Les ventes de ce produit doivent être mises à jour",
            "description": f"Dernière vente enregistrée le {date_label}.",
            "action_label": "Mettre à jour",
        }
    return {
        "state": "current",
        "title": "Ce produit est prêt pour la prévision",
        "description": f"Dernière vente enregistrée le {date_label}.",
        "action_label": "",
    }


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
    freshness_by_product = get_products_freshness(request.company.id)
    selected_product_id = str(form["product_id"].value() or "")
    if not selected_product_id and form.fields["product_id"].choices:
        selected_product_id = str(form.fields["product_id"].choices[0][0])
    freshness_options = {
        product_id: _freshness_presentation(freshness)
        for product_id, freshness in freshness_by_product.items()
    }
    selected_freshness = freshness_options.get(
        selected_product_id, _freshness_presentation(None)
    )
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
        "selected_freshness": selected_freshness,
        "product_freshness_options": freshness_options,
        "max_data_age_days": settings.FORECAST_MAX_DATA_AGE_DAYS,
        "champions": champions,
        "stable_models": stable_models,
        "replacement_threshold": settings.FORECAST_CHAMPION_MIN_IMPROVEMENT,
    })


@company_required
def forecast_result(request, job_id):
    """Présente le résultat métier d'une prévision terminée du dépôt actif."""
    job = get_object_or_404(
        ForecastJob.objects.select_related("requested_by"),
        pk=job_id,
        company=request.company,
        status=ForecastJob.Status.SUCCESS,
        forecast_id__isnull=False,
    )
    with session_for_company(request.company.id) as db:
        service = FutureForecastService(db)
        rows = service.get_forecast_results(str(job.forecast_id))
        stock_snapshot = service.get_product_stock(str(job.product_id))

    results = []
    for row in rows:
        predicted = float(row["predicted_quantity"] or 0)
        prudent = float(row["predicted_p90"] or row["upper_bound"] or predicted)
        results.append({
            **row,
            "predicted_quantity": predicted,
            "predicted_p50": float(row["predicted_p50"] or predicted),
            "predicted_p80": float(row["predicted_p80"] or predicted),
            "predicted_p90": prudent,
            "lower_bound": float(row["lower_bound"] or 0),
            "upper_bound": float(row["upper_bound"] or prudent),
            "predicted_revenue": float(row["predicted_revenue"] or 0),
            "recommended_stock": float(row["recommended_stock"] or 0),
            "actual_quantity": (
                float(row["actual_quantity"])
                if row.get("actual_quantity") is not None
                else None
            ),
        })

    chart_max = max(
        (max(row["predicted_p90"], row["predicted_quantity"]) for row in results),
        default=1,
    ) or 1
    for row in results:
        row["predicted_width"] = max(2, row["predicted_quantity"] / chart_max * 100)
        row["prudent_width"] = max(2, row["predicted_p90"] / chart_max * 100)
        row["safety_margin"] = max(
            0,
            row["predicted_p90"] - row["predicted_quantity"],
        )
        row["safety_margin_width"] = max(
            0,
            row["prudent_width"] - row["predicted_width"],
        )

    predicted_total = sum(row["predicted_quantity"] for row in results)
    uncertainty_buffer = sqrt(sum(row["safety_margin"] ** 2 for row in results))
    operational_reserve = float(stock_snapshot["minimum_stock"])
    safety_margin = uncertainty_buffer + operational_reserve
    current_stock = float(stock_snapshot["current_stock"])
    target_stock = predicted_total + safety_margin
    stock_to_add = max(0.0, target_stock - current_stock)

    projected_stock = current_stock
    remaining_sales = predicted_total
    for row in results:
        row["stock_before"] = projected_stock
        projected_stock = max(0.0, projected_stock - row["predicted_quantity"])
        remaining_sales = max(0.0, remaining_sales - row["predicted_quantity"])
        row["stock_after"] = projected_stock
        remaining_target = remaining_sales + safety_margin
        if row["stock_before"] < row["predicted_quantity"]:
            row["stock_status"] = "RUPTURE"
            row["stock_status_label"] = "Rupture probable"
        elif projected_stock < remaining_target:
            row["stock_status"] = "WATCH"
            row["stock_status_label"] = "À surveiller"
        else:
            row["stock_status"] = "OK"
            row["stock_status_label"] = "Suffisant"

    totals = {
        "quantity": predicted_total,
        "uncertainty_buffer": uncertainty_buffer,
        "operational_reserve": operational_reserve,
        "safety_margin": safety_margin,
        "target_stock": target_stock,
        "current_stock": current_stock,
        "stock_after_period": max(0.0, current_stock - predicted_total),
        "revenue": sum(row["predicted_revenue"] for row in results),
        "stock": stock_to_add,
        "stock_date": stock_snapshot["stock_date"],
    }
    return render(request, "forecasting/result.html", {
        "job": job,
        "results": results,
        "totals": totals,
        "start_date": results[0]["forecast_date"] if results else None,
        "end_date": results[-1]["forecast_date"] if results else None,
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
