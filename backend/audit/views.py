from datetime import date
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render

from companies.models import Company, Membership
from operations.listing import sort_and_paginate
from .models import AuditLog


DEPOT_AUDIT_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
def audit_log_list(request):
    is_platform_audit = request.user.is_active and request.user.is_superuser
    can_view_depot_audit = (
        request.user.is_active
        and getattr(request, "company", None) is not None
        and getattr(request, "membership", None) is not None
        and request.membership.role in DEPOT_AUDIT_ROLES
    )
    if not is_platform_audit and not can_view_depot_audit:
        raise PermissionDenied(
            "Le journal du dépôt est réservé au propriétaire et aux administrateurs."
        )
    query = request.GET.get("q", "").strip()[:100]
    action = request.GET.get("action", "").strip()
    company_id = request.GET.get("company", "").strip()
    try:
        company_id = str(UUID(company_id)) if company_id else ""
    except ValueError:
        company_id = ""
    start = _parse_date(request.GET.get("start"))
    end = _parse_date(request.GET.get("end"))
    logs = AuditLog.objects.select_related("actor", "company")
    if not is_platform_audit:
        company_id = str(request.company.id)
        logs = logs.filter(company=request.company)
    if query:
        logs = logs.filter(
            Q(actor_email__icontains=query)
            | Q(description__icontains=query)
            | Q(resource_type__icontains=query)
            | Q(resource_id__icontains=query)
        )
    if action in AuditLog.Action.values:
        logs = logs.filter(action=action)
    if is_platform_audit and company_id:
        logs = logs.filter(company_id=company_id)
    if start:
        logs = logs.filter(created_at__date__gte=start)
    if end:
        logs = logs.filter(created_at__date__lte=end)
    page_obj, sort_state, pagination_state = sort_and_paginate(
        request, list(logs[:300]),
        allowed_sorts={
            "date": lambda row: row.created_at,
            "user": lambda row: row.actor_email or "",
            "company": lambda row: row.company.name if row.company else "",
            "action": lambda row: row.get_action_display(),
            "event": lambda row: row.description,
            "origin": lambda row: str(row.ip_address or ""),
        },
        default_sort="date", default_direction="desc",
    )
    return render(request, "audit/log_list.html", {
        "logs": page_obj.object_list,
        "page_obj": page_obj, "sort_state": sort_state,
        "pagination_state": pagination_state,
        "actions": AuditLog.Action.choices,
        "companies": Company.objects.order_by("name") if is_platform_audit else (),
        "is_platform_audit": is_platform_audit,
        "filters": {"q": query, "action": action, "company": company_id, "start": start, "end": end},
    })
