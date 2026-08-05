from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q

from companies.models import Company


class RestockDraft(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "À préparer"
        APPROVED = "APPROVED", "Validé"
        CANCELLED = "CANCELLED", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="restock_drafts")
    product_id = models.UUIDField()
    product_name = models.CharField(max_length=180)
    supplier_id = models.UUIDField(null=True, blank=True)
    supplier_name = models.CharField(max_length=180, blank=True)
    forecast_id = models.UUIDField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=16, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    rationale = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="restock_drafts_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restock_drafts"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "product_id"], condition=Q(status="DRAFT"), name="unique_open_restock_draft")
        ]

    def __str__(self):
        return f"{self.product_name} · {self.quantity} colis"
