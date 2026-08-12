from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, RestockDraft


@admin.register(RestockDraft)
class RestockDraftAdmin(admin.ModelAdmin):
    list_display = ("product_name", "company", "quantity", "supplier_name", "status", "updated_at")
    list_filter = ("status", "company")
    search_fields = ("product_name", "supplier_name")
    readonly_fields = ("created_at", "updated_at")


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0
    readonly_fields = (
        "source_draft",
        "product_id",
        "product_code",
        "product_name",
        "quantity_ordered",
        "quantity_received",
        "unit_cost",
    )


class PurchaseOrderReceiptInline(admin.TabularInline):
    model = PurchaseOrderReceipt
    extra = 0
    readonly_fields = (
        "receipt_id",
        "receipt_number",
        "quantity_received",
        "created_by",
        "created_at",
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "company",
        "supplier_name",
        "status",
        "expected_date",
        "created_at",
    )
    list_filter = ("status", "company")
    search_fields = ("order_number", "supplier_name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "sent_at",
        "received_at",
        "cancelled_at",
    )
    inlines = (PurchaseOrderItemInline, PurchaseOrderReceiptInline)
