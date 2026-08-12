from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Membership
from .models import AuditLog
from .services import record_audit


class AuditLogTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="audited@example.com",
            password="A-secure-password-2026",
            full_name="Utilisateur audité",
        )
        self.company = Company.objects.create(code="audit-company", name="Dépôt audité")

    def test_record_audit_keeps_actor_company_and_request_origin(self):
        request = self.factory.post("/produits/nouveau/", REMOTE_ADDR="127.0.0.1", HTTP_USER_AGENT="Test Browser")
        request.user = self.user
        request.company = self.company
        entry = record_audit(
            request,
            action=AuditLog.Action.CREATE,
            resource_type="product",
            resource_id="PRD-TEST",
            description="Création d’un produit de test.",
        )
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.company, self.company)
        self.assertEqual(entry.ip_address, "127.0.0.1")
        self.assertEqual(entry.user_agent, "Test Browser")

    def test_audit_entry_cannot_be_changed_or_deleted_through_model(self):
        entry = AuditLog.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            action=AuditLog.Action.UPDATE,
            resource_type="profile",
            description="Modification du profil.",
        )
        entry.description = "Altération"
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_login_and_logout_are_audited(self):
        self.client.login(email=self.user.email, password="A-secure-password-2026")
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action=AuditLog.Action.LOGIN).exists())
        self.client.post(reverse("accounts:logout"))
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action=AuditLog.Action.LOGOUT).exists())

    def test_audit_page_is_reserved_to_platform_superuser(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("audit:logs")).status_code, 403)
        platform_admin = User.objects.create_superuser(
            email="superaudit@example.com",
            password="A-secure-password-2026",
            full_name="Super audit",
        )
        self.client.force_login(platform_admin)
        response = self.client.get(reverse("audit:logs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Journal d’audit")

    def test_owner_sees_only_the_active_company_activity(self):
        other_company = Company.objects.create(
            code="other-audit-company", name="Autre dépôt"
        )
        Membership.objects.create(
            user=self.user,
            company=self.company,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        AuditLog.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            company=self.company,
            action=AuditLog.Action.CREATE,
            resource_type="product",
            description="Création visible dans le dépôt actif.",
        )
        AuditLog.objects.create(
            actor=self.user,
            actor_email=self.user.email,
            company=other_company,
            action=AuditLog.Action.CREATE,
            resource_type="product",
            description="Création privée dans un autre dépôt.",
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        response = self.client.get(reverse("audit:logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Journal d’activité")
        self.assertContains(response, "Création visible dans le dépôt actif.")
        self.assertNotContains(response, "Création privée dans un autre dépôt.")
        self.assertNotContains(response, 'id="audit-company"')

    def test_viewer_cannot_see_company_activity(self):
        Membership.objects.create(
            user=self.user,
            company=self.company,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        self.assertEqual(self.client.get(reverse("audit:logs")).status_code, 403)
