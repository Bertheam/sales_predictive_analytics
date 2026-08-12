from datetime import date
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


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SENT = "SENT", "Envoyée"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partiellement reçue"
        RECEIVED = "RECEIVED", "Réceptionnée"
        CANCELLED = "CANCELLED", "Annulée"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    order_number = models.CharField(max_length=40)
    supplier_id = models.UUIDField()
    supplier_name = models.CharField(max_length=180)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.DRAFT
    )
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders_updated",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "procurement_orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "order_number"],
                name="unique_company_purchase_order_number",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="proc_order_scope_idx",
            )
        ]

    @classmethod
    def new_number(cls):
        return f"CMD-{date.today():%Y%m%d}-{uuid4().hex[:6].upper()}"

    @property
    def ordered_quantity(self):
        return sum((item.quantity_ordered for item in self.items.all()), 0)

    @property
    def received_quantity(self):
        return sum((item.quantity_received for item in self.items.all()), 0)

    @property
    def remaining_quantity(self):
        return max(self.ordered_quantity - self.received_quantity, 0)

    def __str__(self):
        return f"{self.order_number} · {self.supplier_name}"


class PurchaseOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    source_draft = models.OneToOneField(
        RestockDraft,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_item",
    )
    product_id = models.UUIDField()
    product_code = models.CharField(max_length=40, blank=True)
    product_name = models.CharField(max_length=180)
    quantity_ordered = models.DecimalField(max_digits=16, decimal_places=2)
    quantity_received = models.DecimalField(
        max_digits=16, decimal_places=2, default=0
    )
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "procurement_order_items"
        ordering = ["product_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product_id"],
                name="unique_product_per_purchase_order",
            )
        ]

    @property
    def remaining_quantity(self):
        return max(self.quantity_ordered - self.quantity_received, 0)


class PurchaseOrderReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="receipts"
    )
    receipt_id = models.UUIDField(unique=True)
    receipt_number = models.CharField(max_length=40)
    quantity_received = models.DecimalField(max_digits=16, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="purchase_order_receipts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_order_receipts"
        ordering = ["-created_at"]
