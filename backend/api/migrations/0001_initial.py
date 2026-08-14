# Generated manually for the API idempotency contract.
import uuid

import api.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0006_companyinvitation_channel_companyinvitation_phone_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=128)),
                ("method", models.CharField(max_length=10)),
                ("path", models.CharField(max_length=500)),
                ("request_hash", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("PROCESSING", "En cours"), ("COMPLETED", "Terminée")], default="PROCESSING", max_length=12)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("response_headers", models.JSONField(blank=True, default=dict)),
                ("expires_at", models.DateTimeField(default=api.models.default_idempotency_expiry)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_idempotency_records", to="companies.company")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_idempotency_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "api_idempotency_records"},
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(fields=("user", "company", "method", "path", "key"), name="unique_api_idempotency_scope"),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["expires_at"], name="api_idempotency_expiry_idx"),
        ),
    ]
