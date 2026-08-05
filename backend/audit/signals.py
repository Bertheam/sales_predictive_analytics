from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditLog
from .services import record_audit


@receiver(user_logged_in, dispatch_uid="audit_user_logged_in")
def log_user_login(sender, request, user, **kwargs):
    record_audit(
        request,
        actor=user,
        action=AuditLog.Action.LOGIN,
        resource_type="session",
        description="Connexion réussie à NexaStock.",
    )


@receiver(user_logged_out, dispatch_uid="audit_user_logged_out")
def log_user_logout(sender, request, user, **kwargs):
    record_audit(
        request,
        actor=user,
        action=AuditLog.Action.LOGOUT,
        resource_type="session",
        description="Déconnexion de NexaStock.",
    )


@receiver(user_login_failed, dispatch_uid="audit_user_login_failed")
def log_failed_login(sender, credentials, request, **kwargs):
    identifier = str(credentials.get("username") or credentials.get("email") or "")
    record_audit(
        request,
        actor_email=identifier,
        action=AuditLog.Action.LOGIN_FAILED,
        resource_type="session",
        description="Tentative de connexion refusée.",
    )
