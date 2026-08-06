from datetime import date, timedelta

from django.shortcuts import render
from django.utils import timezone

from companies.permissions import company_required
from .data import get_activity_dashboard, get_overview_snapshot


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _dashboard_period(request):
    today = timezone.localdate()
    shortcut = request.GET.get("period", "").strip()
    if shortcut == "7d":
        return today - timedelta(days=6), today, shortcut
    if shortcut == "30d":
        return today - timedelta(days=29), today, shortcut
    if shortcut == "90d":
        return today - timedelta(days=89), today, shortcut
    if shortcut == "month":
        return today.replace(day=1), today, shortcut
    if shortcut == "year":
        return today.replace(month=1, day=1), today, shortcut

    start_date = _parse_date(request.GET.get("start"))
    end_date = _parse_date(request.GET.get("end"))
    if start_date and end_date and start_date <= end_date:
        return start_date, end_date, "custom"
    return today - timedelta(days=29), today, "30d"


@company_required
def home(request):
    snapshot = get_overview_snapshot(request.company.id, timezone.localdate())
    return render(request, "dashboard/home.html", {
        "snapshot": snapshot,
    })


@company_required
def activity(request):
    start_date, end_date, active_period = _dashboard_period(request)
    dashboard = get_activity_dashboard(request.company.id, start_date, end_date)
    return render(request, "dashboard/activity.html", {
        "dashboard": dashboard,
        "active_period": active_period,
        "filters": {"start": start_date, "end": end_date},
    })
