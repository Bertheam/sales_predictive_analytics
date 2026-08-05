from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from companies.models import Company


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "LOGIN", "Connexion"
        LOGIN_FAILED = "LOGIN_FAILED", "Connexion refusée"
        LOGOUT = "LOGOUT", "Déconnexion"
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        SELECT_COMPANY = "SELECT_COMPANY", "Changement de dépôt"
        IMPORT = "IMPORT", "Import"
        EXPORT = "EXPORT", "Export"
        FORECAST = "FORECAST", "Prévision"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    actor_email = models.EmailField(blank=True)
    company = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    request_id = models.UUIDField(default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "created_at"], name="audit_company_date_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_date_idx"),
            models.Index(fields=["action", "created_at"], name="audit_action_date_idx"),
            models.Index(fields=["resource_type", "resource_id"], name="audit_resource_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Une entrée du journal d’audit ne peut pas être modifiée.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une entrée du journal d’audit ne peut pas être supprimée.")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} · {self.action} · {self.actor_email or 'Système'}"
