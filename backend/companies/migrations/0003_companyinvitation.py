import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0002_simplify_membership_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("role", models.CharField(choices=[("ADMIN", "Administrateur"), ("ANALYST", "Analyste"), ("VIEWER", "Consultation")], default="VIEWER", max_length=12)),
                ("status", models.CharField(choices=[("PENDING", "En attente"), ("ACCEPTED", "Acceptée"), ("REVOKED", "Révoquée"), ("EXPIRED", "Expirée")], default="PENDING", max_length=12)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("accepted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="company_invitations_accepted", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="companies.company")),
                ("invited_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="company_invitations_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "company_invitations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="companyinvitation",
            index=models.Index(fields=["company", "status", "created_at"], name="invitation_company_status_idx"),
        ),
        migrations.AddIndex(
            model_name="companyinvitation",
            index=models.Index(fields=["email", "status"], name="invitation_email_status_idx"),
        ),
    ]
