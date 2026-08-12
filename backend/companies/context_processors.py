from .models import Membership
from .services import company_accesses_for
from .streamlit_access import build_streamlit_access_url


def company_context(request):
    memberships = []
    if request.user.is_authenticated:
        memberships = company_accesses_for(request.user)
    active_membership = getattr(request, "membership", None)
    can_view_audit = bool(
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or (
                active_membership is not None
                and active_membership.role
                in {Membership.Role.OWNER, Membership.Role.ADMIN}
            )
        )
    )
    return {
        "active_company": getattr(request, "company", None),
        "active_membership": getattr(request, "membership", None),
        "available_memberships": memberships,
        "streamlit_url": build_streamlit_access_url(request),
        "is_platform_admin": getattr(request, "is_platform_admin", False),
        "can_view_audit": can_view_audit,
    }
