from django.conf import settings

from .services import company_accesses_for


def company_context(request):
    memberships = []
    if request.user.is_authenticated:
        memberships = company_accesses_for(request.user)
    return {
        "active_company": getattr(request, "company", None),
        "active_membership": getattr(request, "membership", None),
        "available_memberships": memberships,
        "streamlit_url": settings.STREAMLIT_PUBLIC_URL,
        "is_platform_admin": getattr(request, "is_platform_admin", False),
    }
