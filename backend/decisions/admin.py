from django.contrib import admin

from .models import RestockDraft


@admin.register(RestockDraft)
class RestockDraftAdmin(admin.ModelAdmin):
    list_display = ("product_name", "company", "quantity", "supplier_name", "status", "updated_at")
    list_filter = ("status", "company")
    search_fields = ("product_name", "supplier_name")
    readonly_fields = ("created_at", "updated_at")
