from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import Company


def pending_import_expiry():
    return timezone.now() + timedelta(minutes=30)


class PendingDataImport(models.Model):
    """Short-lived Excel upload awaiting explicit user confirmation."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="pending_data_imports",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pending_data_imports",
    )
    import_type = models.CharField(max_length=20)
    original_name = models.CharField(max_length=255)
    content = models.BinaryField()
    file_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=pending_import_expiry)

    class Meta:
        db_table = "pending_data_imports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "created_by", "expires_at"],
                name="pending_import_scope_idx",
            ),
        ]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()
