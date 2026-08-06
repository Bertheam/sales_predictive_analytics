from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from .models import Company, CompanyInvitation, Membership


@dataclass(frozen=True)
class PlatformCompanyAccess:
    company: Company
    role: str = Membership.Role.ADMIN

    @property
    def company_id(self):
        return self.company.id

    def get_role_display(self):
        return "Super administrateur"


def company_accesses_for(user):
    if user.is_superuser:
        return [
            PlatformCompanyAccess(company)
            for company in Company.objects.filter(status=Company.Status.ACTIVE).order_by("name")
        ]
    return list(
        Membership.objects.select_related("company")
        .filter(
            user=user,
            status=Membership.Status.ACTIVE,
            company__status=Company.Status.ACTIVE,
        )
        .order_by("company__name")
    )


def company_management_accesses_for(user):
    """Return the user's depots, including archived ones for restoration."""
    if user.is_superuser:
        return [
            PlatformCompanyAccess(company)
            for company in Company.objects.all().order_by("name")
        ]
    return list(
        Membership.objects.select_related("company")
        .filter(
            user=user,
            status=Membership.Status.ACTIVE,
        )
        .order_by("company__name")
    )


DEFAULT_CATEGORIES = (
    ("EAU", "Eau minérale"),
    ("GAZ", "Boisson gazeuse"),
    ("JUS", "Jus"),
    ("ENERGY", "Boisson énergétique"),
    ("MALT", "Boisson maltée"),
)

DEFAULT_CUSTOMER_TYPES = (
    ("BOUTIQUE", "Boutique"),
    ("RESTAURANT", "Restaurant"),
    ("HOTEL", "Hôtel"),
    ("BAR", "Bar"),
    ("SUPERMARCHE", "Supermarché"),
    ("REVENDEUR", "Revendeur"),
    ("PARTICULIER", "Particulier"),
    ("ENTREPRISE", "Entreprise"),
)

INVITATION_VALIDITY_DAYS = 3


def bootstrap_company_references(company_id) -> None:
    """Create the private reference data required by a new depot."""
    if connection.vendor != "postgresql":
        return
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_company_id', %s, TRUE)",
            [str(company_id)],
        )
        cursor.executemany(
            """
            INSERT INTO product_categories (company_id, code, name, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (company_id, code) DO NOTHING
            """,
            [
                (str(company_id), code, name, "Référentiel initial du dépôt")
                for code, name in DEFAULT_CATEGORIES
            ],
        )
        cursor.executemany(
            """
            INSERT INTO customer_types (company_id, code, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (company_id, code) DO NOTHING
            """,
            [(str(company_id), code, name) for code, name in DEFAULT_CUSTOMER_TYPES],
        )


def team_overview(company):
    members = list(
        Membership.objects.select_related("user")
        .filter(company=company)
        .order_by("role", "user__full_name", "user__email")
    )
    invitations = list(
        CompanyInvitation.objects.select_related("invited_by")
        .filter(company=company, status=CompanyInvitation.Status.PENDING)
        .order_by("-created_at")
    )
    summary = {
        "active": sum(item.status == Membership.Status.ACTIVE for item in members),
        "owners": sum(
            item.status == Membership.Status.ACTIVE
            and item.role == Membership.Role.OWNER
            for item in members
        ),
        "admins": sum(
            item.status == Membership.Status.ACTIVE
            and item.role == Membership.Role.ADMIN
            for item in members
        ),
        "pending": sum(not item.is_expired for item in invitations),
    }
    return members, invitations, summary


def create_or_refresh_invitation(*, company, email, role, invited_by):
    email = email.strip().lower()
    if role not in {
        Membership.Role.ADMIN, Membership.Role.ANALYST, Membership.Role.VIEWER
    }:
        raise ValueError("Ce rôle ne peut pas être attribué par invitation.")
    user = get_user_model().objects.filter(email__iexact=email).first()
    if user and Membership.objects.filter(
        company=company, user=user, status=Membership.Status.ACTIVE
    ).exists():
        raise ValueError("Cette personne fait déjà partie de l’équipe active.")
    with transaction.atomic():
        CompanyInvitation.objects.filter(
            company=company,
            email__iexact=email,
            status=CompanyInvitation.Status.PENDING,
        ).update(status=CompanyInvitation.Status.REVOKED)
        raw_token = token_urlsafe(32)
        invitation = CompanyInvitation.objects.create(
            company=company,
            email=email,
            token_hash=hash_invitation_token(raw_token),
            role=role,
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=INVITATION_VALIDITY_DAYS),
            email_status=CompanyInvitation.EmailStatus.QUEUED,
            email_queued_at=timezone.now(),
        )
        return invitation, raw_token


def renew_invitation_link(invitation):
    """Invalidate the previous link and return a fresh short-lived token."""
    with transaction.atomic():
        invitation = CompanyInvitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.status != CompanyInvitation.Status.PENDING:
            raise ValueError("Cette invitation ne peut plus être renvoyée.")
        raw_token = token_urlsafe(32)
        invitation.token_hash = hash_invitation_token(raw_token)
        invitation.expires_at = timezone.now() + timedelta(days=INVITATION_VALIDITY_DAYS)
        invitation.email_status = CompanyInvitation.EmailStatus.QUEUED
        invitation.email_queued_at = timezone.now()
        invitation.email_sent_at = None
        invitation.email_failed_at = None
        invitation.email_error = ""
        invitation.save(update_fields=[
            "token_hash", "expires_at", "email_status", "email_queued_at",
            "email_sent_at", "email_failed_at", "email_error", "updated_at",
        ])
    return invitation, raw_token


def hash_invitation_token(raw_token):
    return sha256(raw_token.encode("utf-8")).hexdigest()


def accept_company_invitation(invitation, user):
    with transaction.atomic():
        invitation = CompanyInvitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.status != CompanyInvitation.Status.PENDING:
            raise ValueError("Cette invitation n’est plus disponible.")
        if invitation.is_expired:
            invitation.status = CompanyInvitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            raise ValueError("Cette invitation a expiré.")
        if user.email.lower() != invitation.email.lower():
            raise ValueError("Cette invitation est destinée à une autre adresse e-mail.")
        membership, _ = Membership.objects.update_or_create(
            company=invitation.company,
            user=user,
            defaults={
                "role": invitation.role,
                "status": Membership.Status.ACTIVE,
                "joined_at": timezone.now(),
            },
        )
        invitation.status = CompanyInvitation.Status.ACCEPTED
        invitation.accepted_by = user
        invitation.accepted_at = timezone.now()
        invitation.save(
            update_fields=["status", "accepted_by", "accepted_at", "updated_at"]
        )
    return membership


def can_manage_member(actor_membership, target, *, platform_admin=False):
    if platform_admin:
        return target.role != Membership.Role.OWNER
    if actor_membership.user_id == target.user_id:
        return False
    if target.role == Membership.Role.OWNER:
        return False
    if actor_membership.role == Membership.Role.OWNER:
        return True
    return (
        actor_membership.role == Membership.Role.ADMIN
        and target.role in {Membership.Role.ANALYST, Membership.Role.VIEWER}
    )


def update_member_role(*, actor_membership, target, role, platform_admin=False):
    if not can_manage_member(actor_membership, target, platform_admin=platform_admin):
        raise ValueError("Vous ne pouvez pas modifier le rôle de ce membre.")
    allowed = {Membership.Role.ANALYST, Membership.Role.VIEWER}
    if platform_admin or actor_membership.role == Membership.Role.OWNER:
        allowed.add(Membership.Role.ADMIN)
    if role not in allowed:
        raise ValueError("Ce rôle ne peut pas être attribué.")
    target.role = role
    target.save(update_fields=["role", "updated_at"])
    return target


def set_member_suspended(*, actor_membership, target, suspended, platform_admin=False):
    if not can_manage_member(actor_membership, target, platform_admin=platform_admin):
        raise ValueError("Vous ne pouvez pas modifier l’accès de ce membre.")
    target.status = Membership.Status.SUSPENDED if suspended else Membership.Status.ACTIVE
    if not suspended and target.joined_at is None:
        target.joined_at = timezone.now()
    target.save(update_fields=["status", "joined_at", "updated_at"])
    return target
