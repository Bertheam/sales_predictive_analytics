from rest_framework import status
from rest_framework.response import Response

from app.database.tenant import TenantContextError
from companies.tenancy import (
    CompanyAccessDenied,
    bind_company_to_request,
    resolve_company_access,
)


COMPANY_HEADER = "X-Company-ID"


def require_api_company(request):
    """Resolve an explicit API tenant, with session fallback for Django web."""
    header_company_id = request.headers.get(COMPANY_HEADER)
    if header_company_id:
        try:
            access = resolve_company_access(request.user, header_company_id)
        except CompanyAccessDenied:
            return None, Response(
                {
                    "code": "company_access_denied",
                    "detail": "Vous n’avez pas accès à ce dépôt.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except TenantContextError:
            return None, Response(
                {
                    "code": "invalid_company_context",
                    "detail": "L’identifiant du dépôt est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        bind_company_to_request(request, access)

    company = getattr(request, "company", None)
    if company:
        return company, None
    return None, Response(
        {
            "code": "company_context_required",
            "detail": "Sélectionnez un dépôt actif ou transmettez X-Company-ID.",
        },
        status=status.HTTP_409_CONFLICT,
    )
