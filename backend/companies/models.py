from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone


class Company(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        SUSPENDED = "SUSPENDED", "Suspendu"
        ARCHIVED = "ARCHIVED", "Archivé"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    code = models.SlugField("code", max_length=80, unique=True)
    name = models.CharField("nom du dépôt", max_length=180)
    email = models.EmailField("e-mail", blank=True)
    phone = models.CharField("téléphone", max_length=40, blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    currency = models.CharField("devise", max_length=3, default="XOF")
    timezone = models.CharField("fuseau horaire", max_length=50, default="Africa/Bamako")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies"
        verbose_name = "dépôt"
        verbose_name_plural = "dépôts"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Propriétaire"
        ADMIN = "ADMIN", "Administrateur"
        ANALYST = "ANALYST", "Analyste"
        VIEWER = "VIEWER", "Consultation"

    class Status(models.TextChoices):
        INVITED = "INVITED", "Invité"
        ACTIVE = "ACTIVE", "Actif"
        SUSPENDED = "SUSPENDED", "Suspendu"
        REVOKED = "REVOKED", "Révoqué"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_memberships"
        verbose_name = "accès au dépôt"
        verbose_name_plural = "accès aux dépôts"
        constraints = [
            models.UniqueConstraint(fields=["company", "user"], name="unique_company_membership")
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="membership_user_status_idx"),
            models.Index(fields=["company", "role"], name="membership_company_role_idx"),
        ]

    def __str__(self):
        return f"{self.user} · {self.company} · {self.get_role_display()}"


class CompanyInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        ACCEPTED = "ACCEPTED", "Acceptée"
        REVOKED = "REVOKED", "Révoquée"
        EXPIRED = "EXPIRED", "Expirée"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    role = models.CharField(
        max_length=12,
        choices=(
            (Membership.Role.ADMIN, "Administrateur"),
            (Membership.Role.ANALYST, "Analyste"),
            (Membership.Role.VIEWER, "Consultation"),
        ),
        default=Membership.Role.VIEWER,
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="company_invitations_sent",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="company_invitations_accepted",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_invitations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
                name="invitation_company_status_idx",
            ),
            models.Index(fields=["email", "status"], name="invitation_email_status_idx"),
        ]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"{self.email} · {self.company} · {self.get_role_display()}"
