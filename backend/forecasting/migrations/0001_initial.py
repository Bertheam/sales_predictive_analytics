# Generated manually for the initial Celery forecast job registry.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("companies", "0003_companyinvitation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ForecastJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_id", models.UUIDField(verbose_name="produit")),
                ("product_name", models.CharField(max_length=180)),
                ("celery_task_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("status", models.CharField(choices=[("QUEUED", "En attente"), ("RUNNING", "En cours"), ("SUCCESS", "Terminée"), ("FAILED", "Échec")], default="QUEUED", max_length=12)),
                ("horizon", models.PositiveSmallIntegerField(default=7)),
                ("test_days", models.PositiveSmallIntegerField(default=60)),
                ("model_name", models.CharField(blank=True, max_length=120)),
                ("forecast_id", models.UUIDField(blank=True, null=True)),
                ("forecast_number", models.CharField(blank=True, max_length=80)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forecast_jobs", to="companies.company")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forecast_jobs_requested", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "forecast_jobs", "ordering": ["-requested_at"]},
        ),
        migrations.AddIndex(model_name="forecastjob", index=models.Index(fields=["company", "status", "requested_at"], name="forecast_job_company_idx")),
        migrations.AddIndex(model_name="forecastjob", index=models.Index(fields=["company", "product_id", "requested_at"], name="forecast_job_product_idx")),
    ]
