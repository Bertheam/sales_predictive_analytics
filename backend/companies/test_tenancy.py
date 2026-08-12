from uuid import uuid4

from django.test import TestCase

from accounts.models import User
from app.database.tenant import TenantContextError, normalize_company_id

from .models import Company, Membership
from .tenancy import CompanyAccessDenied, resolve_company_access


class TenantIdentifierTests(TestCase):
    def test_company_identifier_is_canonical_and_mandatory(self):
        company_id = uuid4()
        self.assertEqual(normalize_company_id(company_id), str(company_id))
        for invalid in (None, "", "not-a-company"):
            with self.subTest(invalid=invalid), self.assertRaises(TenantContextError):
                normalize_company_id(invalid)


class CompanyAccessResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="tenant-owner@example.com",
            password="A-secure-password-2026",
            full_name="Tenant Owner",
        )
        self.company = Company.objects.create(code="tenant-a", name="Dépôt A")
        self.membership = Membership.objects.create(
            user=self.user,
            company=self.company,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )

    def test_active_membership_resolves_one_company(self):
        access = resolve_company_access(self.user, self.company.id)
        self.assertEqual(access.company, self.company)
        self.assertEqual(access.membership, self.membership)
        self.assertFalse(access.is_platform_admin)

    def test_foreign_company_is_rejected(self):
        foreign = Company.objects.create(code="tenant-b", name="Dépôt B")
        with self.assertRaises(CompanyAccessDenied):
            resolve_company_access(self.user, foreign.id)

    def test_suspended_membership_and_archived_company_are_rejected(self):
        self.membership.status = Membership.Status.SUSPENDED
        self.membership.save(update_fields=["status"])
        with self.assertRaises(CompanyAccessDenied):
            resolve_company_access(self.user, self.company.id)

        self.membership.status = Membership.Status.ACTIVE
        self.membership.save(update_fields=["status"])
        self.company.status = Company.Status.ARCHIVED
        self.company.save(update_fields=["status"])
        with self.assertRaises(CompanyAccessDenied):
            resolve_company_access(self.user, self.company.id)

    def test_platform_superuser_access_is_explicit(self):
        admin = User.objects.create_superuser(
            email="platform-tenant@example.com",
            password="A-secure-password-2026",
            full_name="Platform Admin",
        )
        access = resolve_company_access(admin, self.company.id)
        self.assertTrue(access.is_platform_admin)
        self.assertEqual(access.company, self.company)
        self.assertEqual(access.membership.role, Membership.Role.ADMIN)
