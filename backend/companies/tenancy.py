from dataclasses import dataclass

from app.database.tenant import TenantContextError, normalize_company_id

from .models import Company, Membership
from .services import PlatformCompanyAccess


@dataclass(frozen=True)
class ResolvedCompanyAccess:
    company: Company
    membership: Membership | PlatformCompanyAccess
    is_platform_admin: bool = False


class CompanyAccessDenied(TenantContextError):
    """Raised when an authenticated user cannot use the requested company."""


def resolve_company_access(user, company_id) -> ResolvedCompanyAccess:
    """Resolve one active company without trusting a session, header or UUID."""
    normalized_id = normalize_company_id(company_id)
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        raise CompanyAccessDenied("Un utilisateur actif est requis.")

    if user.is_superuser:
        company = Company.objects.filter(
            id=normalized_id,
            status=Company.Status.ACTIVE,
        ).first()
        if company is None:
            raise CompanyAccessDenied("Ce dépôt n’est pas disponible.")
        return ResolvedCompanyAccess(
            company=company,
            membership=PlatformCompanyAccess(company),
            is_platform_admin=True,
        )

    membership = (
        Membership.objects.select_related("company")
        .filter(
            company_id=normalized_id,
            user=user,
            status=Membership.Status.ACTIVE,
            company__status=Company.Status.ACTIVE,
        )
        .first()
    )
    if membership is None:
        raise CompanyAccessDenied("Vous n’avez pas accès à ce dépôt.")
    return ResolvedCompanyAccess(
        company=membership.company,
        membership=membership,
    )


def bind_company_to_request(request, access: ResolvedCompanyAccess | None) -> None:
    request.company = access.company if access else None
    request.membership = access.membership if access else None
    request.is_platform_admin = bool(access and access.is_platform_admin)
