from django.shortcuts import render

from companies.permissions import company_required
from companies.streamlit_access import build_streamlit_access_url
from .data import get_dashboard_snapshot


@company_required
def home(request):
    snapshot = get_dashboard_snapshot(request.company.id)
    return render(request, "dashboard/home.html", {
        "streamlit_url": build_streamlit_access_url(request),
        "snapshot": snapshot,
    })
