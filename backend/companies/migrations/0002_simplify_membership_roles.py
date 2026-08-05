from django.db import migrations, models


def promote_managers_to_admins(apps, schema_editor):
    Membership = apps.get_model("companies", "Membership")
    Membership.objects.filter(role="MANAGER").update(role="ADMIN")


class Migration(migrations.Migration):
    dependencies = [("companies", "0001_initial")]

    operations = [
        migrations.RunPython(promote_managers_to_admins, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="membership",
            name="role",
            field=models.CharField(
                choices=[
                    ("OWNER", "Propriétaire"),
                    ("ADMIN", "Administrateur"),
                    ("ANALYST", "Analyste"),
                    ("VIEWER", "Consultation"),
                ],
                default="VIEWER",
                max_length=12,
            ),
        ),
    ]
