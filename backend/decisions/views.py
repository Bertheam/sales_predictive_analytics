from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import AuditLog
from audit.services import record_audit
from companies.models import Membership
from companies.permissions import company_required
from operations.data import create_receipt, inventory_history, operational_references

from .forms import (
    ManualPurchaseOrderForm,
    ManualPurchaseOrderItemFormSet,
    PurchaseOrderCreateForm,
    PurchaseOrderReceiveForm,
    RestockDraftForm,
)
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderReceipt,
    RestockDraft,
)
from .services import load_decision_center, load_restock_product


MANAGE_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
RISK_ORDER = {"CRITIQUE": 0, "ÉLEVÉ": 1, "MOYEN": 2, "FAIBLE": 3}


def _order_context(company):
    return {
        "prepared_count": RestockDraft.objects.filter(
            company=company, status=RestockDraft.Status.DRAFT
        ).count(),
        "open_order_count": PurchaseOrder.objects.filter(
            company=company,
            status__in=(
                PurchaseOrder.Status.DRAFT,
                PurchaseOrder.Status.SENT,
                PurchaseOrder.Status.PARTIALLY_RECEIVED,
            ),
        ).count(),
    }


def _get_order(company, order_id, *, lock=False):
    queryset = PurchaseOrder.objects.filter(company=company).prefetch_related(
        "items", "receipts"
    )
    if lock:
        queryset = queryset.select_for_update()
    return get_object_or_404(queryset, id=order_id)


def _receive_form_lines(form):
    return [
        {
            "item": item,
            "quantity_field": form[f"quantity_{item.id}"],
            "unit_cost_field": form[f"unit_cost_{item.id}"],
        }
        for item in form.items
    ]


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
        **_order_context(request.company),
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
        **_order_context(request.company),
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
            **_order_context(request.company),
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


@company_required
def manual_order_create(request):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas de créer une commande fournisseur."
        )
    references = operational_references(request.company.id)
    form = ManualPurchaseOrderForm(
        request.POST or None, suppliers=references["suppliers"]
    )
    items = ManualPurchaseOrderItemFormSet(
        request.POST or None,
        prefix="items",
        form_kwargs={"products": references["products"]},
    )
    if request.method == "POST" and form.is_valid() and items.is_valid():
        supplier = form.selected_supplier()
        products = {str(row["id"]): row for row in references["products"]}
        lines = [
            item.cleaned_data
            for item in items
            if item not in items.deleted_forms
            and item.cleaned_data
            and item.cleaned_data.get("product_id")
        ]
        if supplier is None or any(
            line["product_id"] not in products for line in lines
        ):
            form.add_error(
                None,
                "Un fournisseur ou un produit n’est plus disponible. Actualisez la page.",
            )
        else:
            with transaction.atomic():
                order = PurchaseOrder.objects.create(
                    company=request.company,
                    order_number=PurchaseOrder.new_number(),
                    supplier_id=supplier["id"],
                    supplier_name=supplier["name"],
                    expected_date=form.cleaned_data["expected_date"],
                    notes=form.cleaned_data["notes"],
                    created_by=request.user,
                    updated_by=request.user,
                )
                PurchaseOrderItem.objects.bulk_create(
                    [
                        PurchaseOrderItem(
                            order=order,
                            product_id=products[line["product_id"]]["id"],
                            product_code=products[line["product_id"]]["code"],
                            product_name=products[line["product_id"]]["name"],
                            quantity_ordered=line["quantity_ordered"],
                            unit_cost=products[line["product_id"]]["purchase_price"],
                        )
                        for line in lines
                    ]
                )
            record_audit(
                request,
                action=AuditLog.Action.CREATE,
                resource_type="purchase_order",
                resource_id=order.id,
                description=(
                    f"Création libre de la commande {order.order_number} pour "
                    f"{order.supplier_name}."
                ),
                metadata={
                    "source": "manual",
                    "items": len(lines),
                    "supplier_id": str(order.supplier_id),
                },
            )
            messages.success(
                request,
                f"Commande {order.order_number} créée, indépendamment des recommandations.",
            )
            return redirect("decisions:order-detail", order_id=order.id)
    return render(
        request,
        "decisions/manual_order_form.html",
        {
            "form": form,
            "items": items,
            **_order_context(request.company),
        },
    )


@company_required
def orders(request):
    drafts = list(
        RestockDraft.objects.filter(
            company=request.company, status=RestockDraft.Status.DRAFT
        ).order_by("supplier_name", "product_name")
    )
    groups = {}
    incomplete_drafts = []
    for draft in drafts:
        if not draft.supplier_id:
            incomplete_drafts.append(draft)
            continue
        key = str(draft.supplier_id)
        groups.setdefault(
            key,
            {
                "supplier_id": draft.supplier_id,
                "supplier_name": draft.supplier_name,
                "drafts": [],
                "quantity": Decimal("0"),
            },
        )
        groups[key]["drafts"].append(draft)
        groups[key]["quantity"] += draft.quantity

    queryset = PurchaseOrder.objects.filter(company=request.company).prefetch_related(
        "items"
    )
    status = request.GET.get("status", "open")
    if status == "open":
        queryset = queryset.exclude(
            status__in=(PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED)
        )
    elif status in PurchaseOrder.Status.values:
        queryset = queryset.filter(status=status)
    else:
        status = "all"
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "decisions/orders.html",
        {
            "draft_groups": list(groups.values()),
            "incomplete_drafts": incomplete_drafts,
            "orders": page_obj.object_list,
            "page_obj": page_obj,
            "status_filter": status,
            "can_manage": request.membership.role in MANAGE_ROLES,
            **_order_context(request.company),
        },
    )


@require_POST
@company_required
def create_order(request):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas de créer une commande fournisseur."
        )
    available_drafts = list(
        RestockDraft.objects.filter(
            company=request.company, status=RestockDraft.Status.DRAFT
        )
    )
    form = PurchaseOrderCreateForm(request.POST, drafts=available_drafts)
    if not form.is_valid():
        messages.error(
            request,
            " ".join(
                message
                for messages_list in form.errors.values()
                for message in messages_list
            ),
        )
        return redirect("decisions:orders")

    selected_drafts = form.cleaned_data["selected_drafts"]
    references = operational_references(request.company.id)
    products = {str(row["id"]): row for row in references["products"]}
    suppliers = {str(row["id"]): row for row in references["suppliers"]}
    supplier_id = str(selected_drafts[0].supplier_id)
    supplier = suppliers.get(supplier_id)
    if not supplier:
        messages.error(
            request,
            "Le fournisseur de ces plans n’est plus actif. Choisissez-en un autre.",
        )
        return redirect("decisions:orders")
    if any(str(draft.product_id) not in products for draft in selected_drafts):
        messages.error(
            request,
            "Un produit sélectionné n’est plus actif. Vérifiez les plans préparés.",
        )
        return redirect("decisions:orders")

    with transaction.atomic():
        locked_drafts = list(
            RestockDraft.objects.select_for_update().filter(
                company=request.company,
                id__in=[draft.id for draft in selected_drafts],
                status=RestockDraft.Status.DRAFT,
            )
        )
        if len(locked_drafts) != len(selected_drafts):
            messages.warning(
                request,
                "Un plan vient d’être utilisé. Actualisez la liste avant de recommencer.",
            )
            return redirect("decisions:orders")
        order = PurchaseOrder.objects.create(
            company=request.company,
            order_number=PurchaseOrder.new_number(),
            supplier_id=supplier["id"],
            supplier_name=supplier["name"],
            expected_date=form.cleaned_data["expected_date"],
            notes=form.cleaned_data["notes"],
            created_by=request.user,
            updated_by=request.user,
        )
        PurchaseOrderItem.objects.bulk_create(
            [
                PurchaseOrderItem(
                    order=order,
                    source_draft=draft,
                    product_id=draft.product_id,
                    product_code=products[str(draft.product_id)]["code"],
                    product_name=draft.product_name,
                    quantity_ordered=draft.quantity,
                    unit_cost=products[str(draft.product_id)]["purchase_price"],
                )
                for draft in locked_drafts
            ]
        )
        RestockDraft.objects.filter(id__in=[draft.id for draft in locked_drafts]).update(
            status=RestockDraft.Status.APPROVED
        )

    record_audit(
        request,
        action=AuditLog.Action.CREATE,
        resource_type="purchase_order",
        resource_id=order.id,
        description=(
            f"Création de la commande {order.order_number} pour "
            f"{order.supplier_name}."
        ),
        metadata={"items": len(locked_drafts), "supplier_id": supplier_id},
    )
    messages.success(request, f"Commande {order.order_number} créée en brouillon.")
    return redirect("decisions:order-detail", order_id=order.id)


@company_required
def order_detail(request, order_id):
    order = _get_order(request.company, order_id)
    return render(
        request,
        "decisions/order_detail.html",
        {
            "order": order,
            "can_manage": request.membership.role in MANAGE_ROLES,
            **_order_context(request.company),
        },
    )


@require_POST
@company_required
def send_order(request, order_id):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas de valider une commande fournisseur."
        )
    order = _get_order(request.company, order_id)
    if order.status != PurchaseOrder.Status.DRAFT:
        messages.warning(request, "Seule une commande brouillon peut être marquée envoyée.")
        return redirect("decisions:order-detail", order_id=order.id)
    order.status = PurchaseOrder.Status.SENT
    order.sent_at = timezone.now()
    order.updated_by = request.user
    order.save(update_fields=["status", "sent_at", "updated_by", "updated_at"])
    record_audit(
        request,
        action=AuditLog.Action.UPDATE,
        resource_type="purchase_order",
        resource_id=order.id,
        description=f"Commande {order.order_number} marquée comme envoyée.",
    )
    messages.success(request, f"Commande {order.order_number} marquée comme envoyée.")
    return redirect("decisions:order-detail", order_id=order.id)


@require_POST
@company_required
def cancel_order(request, order_id):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas d’annuler une commande fournisseur."
        )
    order = _get_order(request.company, order_id)
    if order.status in (PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED):
        messages.warning(request, "Cette commande est déjà clôturée.")
        return redirect("decisions:order-detail", order_id=order.id)
    if order.received_quantity > 0:
        messages.error(
            request,
            "Une réception existe déjà pour cette commande ; elle ne peut plus être annulée.",
        )
        return redirect("decisions:order-detail", order_id=order.id)
    order.status = PurchaseOrder.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.updated_by = request.user
    order.save(update_fields=["status", "cancelled_at", "updated_by", "updated_at"])
    record_audit(
        request,
        action=AuditLog.Action.DELETE,
        resource_type="purchase_order",
        resource_id=order.id,
        description=f"Annulation logique de la commande {order.order_number}.",
        metadata={"logical_deletion": True},
    )
    messages.success(request, f"Commande {order.order_number} annulée.")
    return redirect("decisions:orders")


@company_required
def receive_order(request, order_id):
    if request.membership.role not in MANAGE_ROLES:
        return HttpResponseForbidden(
            "Votre rôle ne permet pas de réceptionner une commande fournisseur."
        )
    order = _get_order(request.company, order_id)
    if order.status in (PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED):
        messages.warning(request, "Cette commande ne peut plus recevoir de livraison.")
        return redirect("decisions:order-detail", order_id=order.id)
    form = PurchaseOrderReceiveForm(
        request.POST or None,
        items=list(order.items.all()),
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_order = _get_order(request.company, order_id, lock=True)
            locked_items = {
                str(item.id): item
                for item in PurchaseOrderItem.objects.select_for_update().filter(
                    order=locked_order
                )
            }
            lines = form.receipt_lines()
            for line in lines:
                locked_item = locked_items[str(line["item"].id)]
                if line["quantity_packages"] > locked_item.remaining_quantity:
                    messages.error(
                        request,
                        "Une quantité dépasse le reliquat de la commande. Actualisez la page.",
                    )
                    return redirect("decisions:receive-order", order_id=order.id)
            receipt = create_receipt(
                request.company.id,
                request.user.id,
                {
                    "supplier_id": str(locked_order.supplier_id),
                    "receipt_date": form.cleaned_data["receipt_date"],
                },
                lines,
            )
            received_now = Decimal("0")
            for line in lines:
                item = locked_items[str(line["item"].id)]
                item.quantity_received += line["quantity_packages"]
                item.unit_cost = line["unit_cost"]
                item.save(
                    update_fields=["quantity_received", "unit_cost", "updated_at"]
                )
                received_now += line["quantity_packages"]
            has_remaining = any(
                item.remaining_quantity > 0 for item in locked_items.values()
            )
            locked_order.status = (
                PurchaseOrder.Status.PARTIALLY_RECEIVED
                if has_remaining
                else PurchaseOrder.Status.RECEIVED
            )
            locked_order.received_at = None if has_remaining else timezone.now()
            locked_order.updated_by = request.user
            locked_order.save(
                update_fields=["status", "received_at", "updated_by", "updated_at"]
            )
            PurchaseOrderReceipt.objects.create(
                order=locked_order,
                receipt_id=receipt["id"],
                receipt_number=receipt["number"],
                quantity_received=received_now,
                created_by=request.user,
            )

        record_audit(
            request,
            action=AuditLog.Action.CREATE,
            resource_type="purchase_order_receipt",
            resource_id=receipt["id"],
            description=(
                f"Réception {receipt['number']} liée à la commande "
                f"{order.order_number}."
            ),
            metadata={"order_id": str(order.id), "quantity": str(received_now)},
        )
        messages.success(
            request,
            f"Réception {receipt['number']} enregistrée et stock mis à jour.",
        )
        return redirect("decisions:order-detail", order_id=order.id)
    return render(
        request,
        "decisions/receive_order.html",
        {
            "order": order,
            "form": form,
            "receipt_lines": _receive_form_lines(form),
            **_order_context(request.company),
        },
    )


@company_required
def receipts(request):
    receipt_rows, _ = inventory_history(request.company.id, limit=500)
    page_obj = Paginator(receipt_rows, 25).get_page(request.GET.get("page"))
    linked_receipts = {
        str(link.receipt_id): link.order
        for link in PurchaseOrderReceipt.objects.filter(
            order__company=request.company,
            receipt_id__in=[row["id"] for row in receipt_rows],
        ).select_related("order")
    }
    for row in page_obj.object_list:
        row["order"] = linked_receipts.get(str(row["id"]))
    return render(
        request,
        "decisions/receipts.html",
        {
            "receipts": page_obj.object_list,
            "page_obj": page_obj,
            "can_manage": request.membership.role in MANAGE_ROLES,
            **_order_context(request.company),
        },
    )
