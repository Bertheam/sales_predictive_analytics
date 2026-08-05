from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("forecasting", "0001_initial")]
    operations = [
        migrations.AddConstraint(
            model_name="forecastjob",
            constraint=models.UniqueConstraint(
                fields=("company", "product_id"),
                condition=Q(status__in=["QUEUED", "RUNNING"]),
                name="unique_active_forecast_job",
            ),
        ),
    ]
