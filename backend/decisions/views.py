from decimal import Decimal

from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from audit.models import AuditLog
from audit.services import record_audit
from companies.models import Membership
from companies.permissions import company_required

from .forms import RestockDraftForm
from .models import RestockDraft
from .services import load_decision_center, load_restock_product


MANAGE_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
RISK_ORDER = {"CRITIQUE": 0, "ÉLEVÉ": 1, "MOYEN": 2, "FAIBLE": 3}


@company_required
def center(request):
    data = load_decision_center(request.company.id)
    recommendations = data["recommendations"]
    selected_risk = request.GET.get("risk", "")
    selected_category = request.GET.get("category", "")
    query = request.GET.get("q", "").strip().lower()[:100]
    filtered = [
        row for row in recommendations
        if (not selected_risk or row["risk_level"] == selected_risk)
        and (not selected_category or row["category_name"] == selected_category)
        and (not query or query in row["product_name"].lower() or query in row["product_code"].lower())
    ]
    drafts = {
        str(row.product_id): row
        for row in RestockDraft.objects.filter(
            company=request.company, status=RestockDraft.Status.DRAFT
        )
    }
    for row in filtered:
        row["draft"] = drafts.get(str(row["product_id"]))
    return render(request, "decisions/center.html", {
        **data,
        "recommendations": filtered,
        "categories": sorted({row["category_name"] for row in recommendations}),
        "risks": sorted({row["risk_level"] for row in recommendations}, key=lambda value: RISK_ORDER.get(value, 9)),
        "filters": {"q": request.GET.get("q", ""), "risk": selected_risk, "category": selected_category},
        "can_manage": request.membership.role in MANAGE_ROLES,
    })


@company_required
def product_detail(request, product_id):
    recommendation, suppliers = load_restock_product(request.company.id, product_id)
    if not recommendation:
        raise Http404("Aucune prévision exploitable pour ce produit.")
    draft = RestockDraft.objects.filter(
        company=request.company, product_id=product_id, status=RestockDraft.Status.DRAFT
    ).first()
    form = RestockDraftForm(
        suppliers=suppliers,
        initial={
            "supplier_id": str(draft.supplier_id) if draft and draft.supplier_id else "",
            "quantity": draft.quantity if draft else Decimal(str(round(recommendation["recommended_order"], 2))),
        },
    )
    return render(request, "decisions/product_detail.html", {
        "item": recommendation,
        "form": form,
        "draft": draft,
        "can_manage": request.membership.role in MANAGE_ROLES,
    })


@require_POST
@company_required
def prepare_restock(request, product_id):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden("Votre rôle ne permet pas de préparer un réapprovisionnement.")
    recommendation, suppliers = load_restock_product(request.company.id, product_id)
    if not recommendation:
        raise Http404("Aucune prévision exploitable pour ce produit.")
    form = RestockDraftForm(request.POST, suppliers=suppliers)
    if not form.is_valid():
        return render(request, "decisions/product_detail.html", {
            "item": recommendation, "form": form, "draft": None, "can_manage": True,
        }, status=400)
    supplier = form.selected_supplier()
    draft, created = RestockDraft.objects.update_or_create(
        company=request.company,
        product_id=product_id,
        status=RestockDraft.Status.DRAFT,
        defaults={
            "product_name": recommendation["product_name"],
            "supplier_id": supplier["id"] if supplier else None,
            "supplier_name": supplier["name"] if supplier else "",
            "forecast_id": recommendation["forecast_id"],
            "quantity": form.cleaned_data["quantity"],
            "created_by": request.user,
            "rationale": {
                "current_stock": recommendation["current_stock"],
                "predicted_p50": recommendation["predicted_quantity"],
                "predicted_p90": recommendation["p90_quantity"],
                "safety_stock": recommendation["safety_stock"],
                "risk_level": recommendation["risk_level"],
            },
        },
    )
    record_audit(
        request,
        action=AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE,
        resource_type="restock_draft",
        resource_id=draft.id,
        description=f"Plan de réapprovisionnement préparé pour {draft.product_name} : {draft.quantity} colis.",
        metadata={"supplier": draft.supplier_name, "forecast_id": str(draft.forecast_id)},
    )
    messages.success(request, f"Le réapprovisionnement de {draft.product_name} a été préparé.")
    return redirect("decisions:product-detail", product_id=product_id)
