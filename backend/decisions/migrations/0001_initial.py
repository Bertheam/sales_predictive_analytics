import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [("companies", "0003_companyinvitation"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="RestockDraft",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_id", models.UUIDField()),
                ("product_name", models.CharField(max_length=180)),
                ("supplier_id", models.UUIDField(blank=True, null=True)),
                ("supplier_name", models.CharField(blank=True, max_length=180)),
                ("forecast_id", models.UUIDField(blank=True, null=True)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=16)),
                ("status", models.CharField(choices=[("DRAFT", "À préparer"), ("APPROVED", "Validé"), ("CANCELLED", "Annulé")], default="DRAFT", max_length=12)),
                ("rationale", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="restock_drafts", to="companies.company")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="restock_drafts_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "restock_drafts", "ordering": ["-updated_at"]},
        ),
        migrations.AddConstraint(model_name="restockdraft", constraint=models.UniqueConstraint(fields=("company", "product_id"), condition=Q(status="DRAFT"), name="unique_open_restock_draft")),
    ]
