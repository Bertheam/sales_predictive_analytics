# Generated manually to keep the migration deterministic.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import operations.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0005_invitation_brevo_message_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingDataImport",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True,
                        serialize=False,
                    ),
                ),
                ("import_type", models.CharField(max_length=20)),
                ("original_name", models.CharField(max_length=255)),
                ("content", models.BinaryField()),
                ("file_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expires_at",
                    models.DateTimeField(default=operations.models.pending_import_expiry),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_data_imports",
                        to="companies.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_data_imports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "pending_data_imports",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pendingdataimport",
            index=models.Index(
                fields=["company", "created_by", "expires_at"],
                name="pending_import_scope_idx",
            ),
        ),
    ]
