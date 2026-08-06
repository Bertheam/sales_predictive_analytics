from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("companies", "0004_invitation_email_delivery")]

    operations = [
        migrations.AddField(
            model_name="companyinvitation",
            name="email_message_id",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
