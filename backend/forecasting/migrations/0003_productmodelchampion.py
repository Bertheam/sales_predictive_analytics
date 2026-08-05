import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0003_companyinvitation"),
        ("forecasting", "0002_unique_active_job"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductModelChampion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_id", models.UUIDField(verbose_name="produit")),
                ("product_name", models.CharField(max_length=180)),
                ("model_key", models.CharField(max_length=80)),
                ("model_label", models.CharField(max_length=120)),
                ("mae", models.FloatField(blank=True, null=True)),
                ("rmse", models.FloatField(blank=True, null=True)),
                ("mape", models.FloatField(blank=True, null=True)),
                ("wape", models.FloatField(blank=True, null=True)),
                ("bias", models.FloatField(blank=True, null=True)),
                ("challenger_key", models.CharField(blank=True, max_length=80)),
                ("challenger_label", models.CharField(blank=True, max_length=120)),
                ("challenger_mae", models.FloatField(blank=True, null=True)),
                ("improvement_percentage", models.FloatField(blank=True, null=True)),
                ("last_decision", models.CharField(choices=[("INSTALLED", "Premier modèle installé"), ("RETAINED", "Modèle conservé"), ("REPLACED", "Nouveau modèle adopté")], default="INSTALLED", max_length=12)),
                ("decision_reason", models.CharField(blank=True, max_length=255)),
                ("champion_since", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_evaluated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forecast_model_champions", to="companies.company")),
            ],
            options={"db_table": "product_model_champions", "ordering": ["product_name"]},
        ),
        migrations.AddConstraint(
            model_name="productmodelchampion",
            constraint=models.UniqueConstraint(fields=("company", "product_id"), name="unique_product_model_champion"),
        ),
    ]
