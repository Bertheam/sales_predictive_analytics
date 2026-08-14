from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import Company


def default_idempotency_expiry():
    return timezone.now() + timedelta(days=7)


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "En cours"
        COMPLETED = "COMPLETED", "Terminée"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    key = models.CharField(max_length=128)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="api_idempotency_records",
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="api_idempotency_records"
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PROCESSING
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(
        default=default_idempotency_expiry
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_idempotency_records"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "company", "method", "path", "key"),
                name="unique_api_idempotency_scope",
            )
        ]
        indexes = [
            models.Index(fields=("expires_at",), name="api_idempotency_expiry_idx")
        ]
