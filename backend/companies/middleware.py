from django.core.exceptions import ValidationError

from .models import Company, Membership
from .services import PlatformCompanyAccess


class ActiveCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.membership = None
        request.is_platform_admin = False
        if request.user.is_authenticated:
            company_id = request.session.get("active_company_id")
            if request.user.is_superuser and company_id:
                try:
                    company = Company.objects.filter(
                        id=company_id, status=Company.Status.ACTIVE
                    ).first()
                except (ValidationError, ValueError):
                    company = None
                if company:
                    request.company = company
                    request.membership = PlatformCompanyAccess(company)
                    request.is_platform_admin = True
                    return self.get_response(request)
            try:
                membership = (
                    Membership.objects.select_related("company")
                    .filter(
                        company_id=company_id,
                        user=request.user,
                        status=Membership.Status.ACTIVE,
                        company__status=Company.Status.ACTIVE,
                    )
                    .first()
                )
            except (ValidationError, ValueError):
                membership = None
            if membership:
                request.company = membership.company
                request.membership = membership
            elif company_id:
                request.session.pop("active_company_id", None)
        return self.get_response(request)
