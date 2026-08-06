from io import StringIO
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Company, CompanyInvitation, Membership
from .services import hash_invitation_token


class CompanyFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="A-secure-password-2026", full_name="Moussa Diallo"
        )
        self.client.force_login(self.user)

    @patch("companies.views.bootstrap_company_references")
    def test_onboarding_creates_owner_membership_and_selects_company(self, _bootstrap):
        response = self.client.post(reverse("companies:onboarding"), {
            "name": "Dépôt Horizon",
            "phone": "+22370000000",
            "email": "contact@horizon.test",
            "city": "Bamako",
        })
        company = Company.objects.get(name="Dépôt Horizon")
        membership = Membership.objects.get(company=company, user=self.user)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(self.client.session["active_company_id"], str(company.pk))
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_user_cannot_select_another_company(self):
        foreign = Company.objects.create(code="foreign-001", name="Dépôt sans accès")
        response = self.client.post(reverse("companies:select"), {"company_id": str(foreign.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("active_company_id", self.client.session)

    def test_invalid_company_identifier_is_rejected(self):
        response = self.client.post(reverse("companies:select"), {"company_id": "not-a-valid-id"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("active_company_id", self.client.session)

    def test_dashboard_requires_company_context(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(response, reverse("companies:onboarding"))

    def test_legacy_company_can_be_claimed_by_email(self):
        legacy = Company.objects.create(
            id="00000000-0000-4000-8000-000000000001",
            code="depot-historique",
            name="Dépôt historique",
        )
        output = StringIO()
        call_command("claim_legacy_company", self.user.email, stdout=output)
        membership = Membership.objects.get(company=legacy, user=self.user)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.status, Membership.Status.ACTIVE)

    def test_dashboard_renders_for_selected_company(self):
        company = Company.objects.create(code="selected", name="Dépôt sélectionné")
        Membership.objects.create(
            company=company,
            user=self.user,
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dépôt sélectionné")

    def test_sidebar_picker_switches_company_and_keeps_current_page(self):
        first = Company.objects.create(code="first-depot", name="Dépôt Central")
        second = Company.objects.create(code="second-depot", name="Dépôt Nord")
        for company in (first, second):
            Membership.objects.create(
                company=company,
                user=self.user,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
            )
        session = self.client.session
        session["active_company_id"] = str(first.id)
        session.save()

        dashboard = self.client.get(reverse("dashboard:home"))
        self.assertContains(dashboard, "Changer de dépôt", count=1)
        self.assertContains(dashboard, "Dépôt Central")
        self.assertContains(dashboard, "Dépôt Nord")

        response = self.client.post(reverse("companies:select"), {
            "company_id": str(second.id),
            "next": reverse("operations:products"),
        })
        self.assertRedirects(
            response,
            reverse("operations:products"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session["active_company_id"], str(second.id))

    def test_company_switcher_rejects_an_external_return_url(self):
        company = Company.objects.create(code="safe-depot", name="Dépôt sûr")
        Membership.objects.create(
            company=company,
            user=self.user,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        response = self.client.post(reverse("companies:select"), {
            "company_id": str(company.id),
            "next": "https://example.net/redirect",
        })
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_platform_superuser_can_select_any_active_company(self):
        platform_admin = User.objects.create_superuser(
            email="platform@example.com",
            password="A-secure-password-2026",
            full_name="Super administrateur",
        )
        company = Company.objects.create(code="platform-depot", name="Dépôt plateforme")
        self.client.force_login(platform_admin)
        response = self.client.post(reverse("companies:select"), {
            "company_id": str(company.id),
        })
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertEqual(self.client.session["active_company_id"], str(company.id))
        dashboard = self.client.get(reverse("dashboard:home"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Super administrateur")

    def test_owner_can_edit_company_information(self):
        company = Company.objects.create(code="editable-depot", name="Ancien nom")
        Membership.objects.create(
            company=company,
            user=self.user,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        response = self.client.post(reverse("companies:edit", args=[company.id]), {
            "name": "Dépôt Central",
            "phone": "+22370000000",
            "email": "central@example.com",
            "city": "Bamako",
            "currency": "xof",
            "timezone": "Africa/Bamako",
        })
        company.refresh_from_db()
        self.assertRedirects(response, reverse("companies:list"))
        self.assertEqual(company.name, "Dépôt Central")
        self.assertEqual(company.currency, "XOF")

    def test_non_owner_cannot_edit_company(self):
        company = Company.objects.create(code="viewer-depot", name="Dépôt lecture")
        Membership.objects.create(
            company=company,
            user=self.user,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
        )
        response = self.client.get(reverse("companies:edit", args=[company.id]))
        self.assertEqual(response.status_code, 403)

    def test_archive_is_logical_and_archived_company_can_be_restored(self):
        company = Company.objects.create(code="archive-depot", name="Dépôt à archiver")
        Membership.objects.create(
            company=company,
            user=self.user,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()

        response = self.client.post(reverse("companies:status", args=[company.id]), {
            "action": "archive",
        })
        company.refresh_from_db()
        self.assertRedirects(response, reverse("companies:list"))
        self.assertEqual(company.status, Company.Status.ARCHIVED)
        self.assertNotIn("active_company_id", self.client.session)
        self.assertContains(self.client.get(reverse("companies:list")), "Dépôt à archiver")

        response = self.client.post(reverse("companies:status", args=[company.id]), {
            "action": "restore",
        })
        company.refresh_from_db()
        self.assertRedirects(response, reverse("companies:list"))
        self.assertEqual(company.status, Company.Status.ACTIVE)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TeamManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-team@example.com",
            password="A-secure-password-2026",
            full_name="Propriétaire Test",
        )
        self.company = Company.objects.create(code="team-depot", name="Dépôt Équipe")
        self.owner_membership = Membership.objects.create(
            company=self.company,
            user=self.owner,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

    def create_member(self, role=Membership.Role.VIEWER, status=Membership.Status.ACTIVE):
        user = User.objects.create_user(
            email=f"member-{uuid4().hex[:8]}@example.com",
            password="A-secure-password-2026",
            full_name="Membre Test",
        )
        membership = Membership.objects.create(
            company=self.company,
            user=user,
            role=role,
            status=status,
            joined_at=timezone.now(),
        )
        return user, membership

    def test_owner_can_open_team_page(self):
        response = self.client.get(reverse("companies:team"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Équipe du dépôt")
        self.assertContains(response, self.owner.email)
        self.assertContains(response, "data-submit-lock")
        self.assertContains(response, 'data-loading-label="Envoi en cours…"')

    def test_viewer_cannot_open_team_page(self):
        viewer, membership = self.create_member()
        self.client.force_login(viewer)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()
        self.assertEqual(self.client.get(reverse("companies:team")).status_code, 403)

    def test_owner_can_create_email_invitation(self):
        response = self.client.post(reverse("companies:team-invite"), {
            "email": "future@example.com", "role": Membership.Role.ADMIN,
        })
        invitation = CompanyInvitation.objects.get(email="future@example.com")
        self.assertEqual(invitation.role, Membership.Role.ADMIN)
        self.assertRedirects(response, reverse("companies:team"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(invitation.token_hash, mail.outbox[0].body)
        self.assertIn(self.company.name, mail.outbox[0].body)
        self.assertIn("Administrateur", mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        html_body, content_type = mail.outbox[0].alternatives[0]
        self.assertEqual(content_type, "text/html")
        self.assertIn("Entrer dans mon dépôt", html_body)
        self.assertIn(self.company.name, html_body)

    def test_active_member_cannot_be_invited_twice(self):
        user, _ = self.create_member()
        response = self.client.post(reverse("companies:team-invite"), {
            "email": user.email, "role": Membership.Role.VIEWER,
        })
        self.assertRedirects(response, reverse("companies:team"))
        self.assertFalse(CompanyInvitation.objects.filter(email=user.email).exists())

    def test_new_user_can_accept_invitation(self):
        raw_token = "new-member-secure-token"
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="new-member@example.com",
            token_hash=hash_invitation_token(raw_token),
            role=Membership.Role.ANALYST,
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=3),
        )
        self.client.logout()
        response = self.client.post(
            reverse("companies:invitation-accept", args=[raw_token]),
            {
                "full_name": "Nouvel Analyste",
                "password1": "Mot-de-passe-solide-2026!",
                "password2": "Mot-de-passe-solide-2026!",
            },
        )
        user = User.objects.get(email=invitation.email)
        membership = Membership.objects.get(company=self.company, user=user)
        invitation.refresh_from_db()
        self.assertEqual(membership.role, Membership.Role.ANALYST)
        self.assertEqual(membership.status, Membership.Status.ACTIVE)
        self.assertEqual(invitation.status, CompanyInvitation.Status.ACCEPTED)
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_expired_invitation_is_unavailable(self):
        raw_token = "expired-secure-token"
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="expired@example.com",
            token_hash=hash_invitation_token(raw_token),
            role=Membership.Role.VIEWER,
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.logout()
        response = self.client.get(
            reverse("companies:invitation-accept", args=[raw_token])
        )
        self.assertEqual(response.status_code, 410)

    def test_owner_can_change_member_role(self):
        _, membership = self.create_member()
        response = self.client.post(
            reverse("companies:member-edit", args=[membership.id]),
            {"role": Membership.Role.ADMIN},
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, Membership.Role.ADMIN)
        self.assertRedirects(response, reverse("companies:team"))

    def test_owner_cannot_suspend_own_access(self):
        response = self.client.post(
            reverse("companies:member-access", args=[self.owner_membership.id]),
            {"action": "suspend"},
        )
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.status, Membership.Status.ACTIVE)
        self.assertRedirects(response, reverse("companies:team"))

    def test_admin_cannot_manage_another_admin(self):
        admin, admin_membership = self.create_member(role=Membership.Role.ADMIN)
        _, other_admin = self.create_member(role=Membership.Role.ADMIN)
        self.client.force_login(admin)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()
        response = self.client.post(
            reverse("companies:member-edit", args=[other_admin.id]),
            {"role": Membership.Role.VIEWER},
        )
        self.assertEqual(response.status_code, 403)
        other_admin.refresh_from_db()
        self.assertEqual(other_admin.role, Membership.Role.ADMIN)
