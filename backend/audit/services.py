from ipaddress import ip_address

from django.conf import settings

from .models import AuditLog


def _client_ip(request):
    if not request:
        return None
    value = request.META.get("REMOTE_ADDR", "")
    if settings.AUDIT_TRUST_X_FORWARDED_FOR:
        value = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip() or value
    try:
        return str(ip_address(value)) if value else None
    except ValueError:
        return None


def record_audit(
    request,
    *,
    action,
    resource_type,
    description,
    resource_id="",
    company=None,
    actor=None,
    actor_email="",
    metadata=None,
):
    request_user = getattr(request, "user", None) if request else None
    if actor is None and getattr(request_user, "is_authenticated", False):
        actor = request_user
    company = company or (getattr(request, "company", None) if request else None)
    email = actor_email or (getattr(actor, "email", "") if actor else "")
    return AuditLog.objects.create(
        actor=actor,
        actor_email=email[:254],
        company=company,
        action=action,
        resource_type=resource_type[:80],
        resource_id=str(resource_id or "")[:100],
        description=description[:500],
        metadata=metadata or {},
        ip_address=_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
    )
