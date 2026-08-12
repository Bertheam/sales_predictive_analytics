from uuid import UUID


class TenantContextError(ValueError):
    """Raised when a business database scope has no valid company identifier."""


def normalize_company_id(company_id) -> str:
    """Return one canonical tenant UUID and reject implicit/global scopes."""
    if company_id in (None, ""):
        raise TenantContextError("Un dépôt explicite est requis pour cette opération.")
    try:
        return str(UUID(str(company_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TenantContextError("L’identifiant du dépôt est invalide.") from exc
