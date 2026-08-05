from django.conf import settings
from django.shortcuts import render

from companies.permissions import company_required
from .data import get_dashboard_snapshot


@company_required
def home(request):
    snapshot = get_dashboard_snapshot(request.company.id)
    return render(request, "dashboard/home.html", {
        "streamlit_url": settings.STREAMLIT_PUBLIC_URL,
        "snapshot": snapshot,
    })
