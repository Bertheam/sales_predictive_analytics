from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from companies.models import Company


class ForecastJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "En attente"
        RUNNING = "RUNNING", "En cours"
        SUCCESS = "SUCCESS", "Terminée"
        FAILED = "FAILED", "Échec"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="forecast_jobs"
    )
    product_id = models.UUIDField("produit")
    product_name = models.CharField(max_length=180)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forecast_jobs_requested",
    )
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.QUEUED
    )
    horizon = models.PositiveSmallIntegerField(default=7)
    test_days = models.PositiveSmallIntegerField(default=60)
    model_name = models.CharField(max_length=120, blank=True)
    forecast_id = models.UUIDField(null=True, blank=True)
    forecast_number = models.CharField(max_length=80, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "forecast_jobs"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "requested_at"],
                name="forecast_job_company_idx",
            ),
            models.Index(
                fields=["company", "product_id", "requested_at"],
                name="forecast_job_product_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "product_id"],
                condition=Q(status__in=["QUEUED", "RUNNING"]),
                name="unique_active_forecast_job",
            )
        ]

    def __str__(self):
        return f"{self.product_name} · {self.get_status_display()}"


class ProductModelChampion(models.Model):
    """Modèle de prévision actuellement approuvé pour un produit du dépôt."""

    class Decision(models.TextChoices):
        INSTALLED = "INSTALLED", "Premier modèle installé"
        RETAINED = "RETAINED", "Modèle conservé"
        REPLACED = "REPLACED", "Nouveau modèle adopté"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="forecast_model_champions"
    )
    product_id = models.UUIDField("produit")
    product_name = models.CharField(max_length=180)
    model_key = models.CharField(max_length=80)
    model_label = models.CharField(max_length=120)
    mae = models.FloatField(null=True, blank=True)
    rmse = models.FloatField(null=True, blank=True)
    mape = models.FloatField(null=True, blank=True)
    wape = models.FloatField(null=True, blank=True)
    bias = models.FloatField(null=True, blank=True)
    challenger_key = models.CharField(max_length=80, blank=True)
    challenger_label = models.CharField(max_length=120, blank=True)
    challenger_mae = models.FloatField(null=True, blank=True)
    improvement_percentage = models.FloatField(null=True, blank=True)
    last_decision = models.CharField(
        max_length=12, choices=Decision.choices, default=Decision.INSTALLED
    )
    decision_reason = models.CharField(max_length=255, blank=True)
    champion_since = models.DateTimeField(default=timezone.now)
    last_evaluated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_model_champions"
        ordering = ["product_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "product_id"],
                name="unique_product_model_champion",
            )
        ]

    def __str__(self):
        return f"{self.product_name} · {self.model_label}"
