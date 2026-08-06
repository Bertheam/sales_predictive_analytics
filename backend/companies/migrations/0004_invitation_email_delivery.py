from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0003_companyinvitation")]

    operations = [
        migrations.AddField(
            model_name="companyinvitation",
            name="email_status",
            field=models.CharField(
                choices=[
                    ("UNKNOWN", "Statut non suivi"),
                    ("QUEUED", "En attente d’envoi"),
                    ("SENDING", "Envoi en cours"),
                    ("SENT", "Accepté par Brevo"),
                    ("FAILED", "Échec de l’envoi"),
                ],
                default="UNKNOWN",
                max_length=12,
            ),
        ),
        migrations.AddField(model_name="companyinvitation", name="email_attempts", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="companyinvitation", name="email_queued_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="companyinvitation", name="email_sent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="companyinvitation", name="email_failed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="companyinvitation", name="email_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="companyinvitation", name="last_email_task_id", field=models.CharField(blank=True, max_length=255)),
    ]
