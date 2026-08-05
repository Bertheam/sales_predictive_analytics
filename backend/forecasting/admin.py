from django.contrib import admin

from .models import ForecastJob, ProductModelChampion


@admin.register(ForecastJob)
class ForecastJobAdmin(admin.ModelAdmin):
    list_display = ("product_name", "company", "status", "model_name", "requested_at")
    list_filter = ("status", "company")
    search_fields = ("product_name", "forecast_number", "celery_task_id")
    readonly_fields = ("requested_at", "started_at", "completed_at")


@admin.register(ProductModelChampion)
class ProductModelChampionAdmin(admin.ModelAdmin):
    list_display = (
        "product_name", "company", "model_label", "last_decision", "last_evaluated_at"
    )
    list_filter = ("last_decision", "company")
    search_fields = ("product_name", "model_label", "challenger_label")
    readonly_fields = ("created_at", "updated_at", "last_evaluated_at")
