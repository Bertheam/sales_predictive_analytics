from urllib.parse import urlencode

from django import template


register = template.Library()


STATUS_LABELS = {
    "PAID": "Payée",
    "UNPAID": "À payer",
    "PARTIAL": "Partiellement payée",
    "CANCELLED": "Annulée",
    "ACTIVE": "Actif",
    "INACTIVE": "Inactif",
    "ARCHIVED": "Archivé",
    "PENDING": "En attente",
    "DRAFT": "Brouillon",
    "SENT": "Envoyée",
    "APPROVED": "Intégré à une commande",
    "PARTIALLY_RECEIVED": "Partiellement reçue",
    "RECEIVED": "Réceptionnée",
    "COMPLETED": "Terminée",
    "PARTIALLY_COMPLETED": "Terminée avec alertes",
    "IMPORTING": "Import en cours",
    "VALIDATING": "Vérification en cours",
    "VALIDATED": "Vérifiée",
    "SUCCESS": "Terminée",
    "FAILED": "Échec",
    "CRITICAL": "Critique",
    "HIGH": "Élevée",
    "MEDIUM": "Modérée",
    "LOW": "Faible",
}

STATUS_VARIANTS = {
    "PAID": "success", "SUCCESS": "success", "COMPLETED": "success",
    "PARTIALLY_COMPLETED": "warning", "IMPORTING": "warning",
    "VALIDATING": "warning", "VALIDATED": "success",
    "ACTIVE": "success", "UNPAID": "warning", "PARTIAL": "warning",
    "PENDING": "warning", "DRAFT": "neutral", "SENT": "warning",
    "APPROVED": "success", "PARTIALLY_RECEIVED": "warning",
    "RECEIVED": "success", "HIGH": "warning", "MEDIUM": "warning",
    "CANCELLED": "danger", "FAILED": "danger", "CRITICAL": "danger",
}

PAYMENT_METHOD_LABELS = {
    "CASH": "Espèces",
    "MOBILE_MONEY": "Mobile Money",
    "BANK_TRANSFER": "Virement bancaire",
    "CREDIT": "Crédit",
}


def _query_url(request, updates):
    query = request.GET.copy()
    for key, value in updates.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.inclusion_tag("components/sortable_header.html", takes_context=True)
def sortable_header(context, label, field, state):
    active = state.field == field
    next_direction = "desc" if active and state.direction == "asc" else "asc"
    return {
        "label": label,
        "active": active,
        "direction": state.direction if active else "",
        "url": _query_url(context["request"], {
            state.sort_param: field,
            state.direction_param: next_direction,
            state.page_param: None,
        }),
    }


@register.inclusion_tag("components/pagination.html", takes_context=True)
def pagination(context, page_obj, state):
    request = context["request"]
    pages = []
    for number in page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    ):
        pages.append({
            "label": number,
            "current": number == page_obj.number,
            "ellipsis": number == page_obj.paginator.ELLIPSIS,
            "url": None if number == page_obj.paginator.ELLIPSIS else _query_url(
                request, {state.page_param: number}
            ),
        })
    return {
        "page_obj": page_obj,
        "pages": pages,
        "previous_url": _query_url(
            request, {state.page_param: page_obj.previous_page_number()}
        ) if page_obj.has_previous() else "",
        "next_url": _query_url(
            request, {state.page_param: page_obj.next_page_number()}
        ) if page_obj.has_next() else "",
    }


@register.filter
def status_label(value):
    return STATUS_LABELS.get(str(value or "").upper(), value or "—")


@register.filter
def status_variant(value):
    return STATUS_VARIANTS.get(str(value or "").upper(), "neutral")


@register.filter
def payment_method_label(value):
    return PAYMENT_METHOD_LABELS.get(str(value or "").upper(), value or "—")


@register.filter
def business_name(value):
    """Keep internal codes out of task-first headings while preserving stored labels."""
    return str(value or "").split(" · ", 1)[0]


@register.filter
def import_type_label(value):
    return {
        "SALES": "Ventes",
        "STOCKS": "Stocks journaliers",
        "PRODUCTS": "Produits",
        "CUSTOMERS": "Clients",
    }.get(str(value or "").upper(), value or "—")
