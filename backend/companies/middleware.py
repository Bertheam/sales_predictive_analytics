from app.database.tenant import TenantContextError

from .tenancy import (
    CompanyAccessDenied,
    bind_company_to_request,
    resolve_company_access,
)


class ActiveCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bind_company_to_request(request, None)
        if request.user.is_authenticated:
            company_id = request.session.get("active_company_id")
            if company_id:
                try:
                    access = resolve_company_access(request.user, company_id)
                except (TenantContextError, CompanyAccessDenied):
                    access = None
                if access:
                    bind_company_to_request(request, access)
                else:
                    request.session.pop("active_company_id", None)
        return self.get_response(request)
