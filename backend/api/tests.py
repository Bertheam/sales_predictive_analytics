from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from companies.models import Company, Membership


class ApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="api@example.com", password="A-secure-password-2026", full_name="API User"
        )
        self.company = Company.objects.create(code="api-depot", name="Dépôt API")
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.ADMIN, status=Membership.Status.ACTIVE
        )

    def test_api_rejects_anonymous_requests(self):
        response = self.client.get(reverse("api:me"))
        self.assertIn(response.status_code, (401, 403))

    def test_context_returns_only_selected_company_and_role(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        response = self.client.get(reverse("api:context"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company"]["code"], "api-depot")
        self.assertEqual(response.json()["role"], Membership.Role.ADMIN)

    def test_companies_returns_user_memberships(self):
        Company.objects.create(code="other", name="Autre dépôt")
        self.client.force_login(self.user)
        response = self.client.get(reverse("api:companies"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["company"]["code"], "api-depot")

    def test_dashboard_summary_requires_selected_company(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("api:dashboard-summary"))
        self.assertEqual(response.status_code, 409)

    def test_dashboard_summary_uses_selected_company(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        response = self.client.get(reverse("api:dashboard-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(self.company.pk))

    def test_operational_api_requires_selected_company(self):
        self.client.force_login(self.user)
        for route in ("api:products", "api:stocks", "api:sales"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 409)

    def test_operational_api_is_scoped_to_selected_company(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        for route in ("api:products", "api:stocks", "api:sales"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["company_id"], str(self.company.pk))

    def test_authorized_company_header_works_without_browser_session(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(self.company.id))

    def test_explicit_company_header_overrides_browser_session(self):
        second = Company.objects.create(code="api-second", name="Second dépôt")
        Membership.objects.create(
            user=self.user,
            company=second,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(second.id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(second.id))

    def test_foreign_company_header_is_rejected_without_fallback(self):
        foreign = Company.objects.create(code="api-foreign", name="Dépôt étranger")
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(foreign.id),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "company_access_denied")

    def test_invalid_company_header_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID="invalid-company",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_company_context")

    def test_mobile_login_returns_jwt_and_accessible_companies(self):
        response = self.client.post(
            reverse("api:login"),
            {"identifier": self.user.email, "password": "A-secure-password-2026"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
        self.assertEqual(len(response.json()["companies"]), 1)

    def test_bearer_authentication_accesses_profile(self):
        access = str(RefreshToken.for_user(self.user).access_token)
        response = self.client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.user.email)

    def test_viewer_cannot_create_stock_movement(self):
        membership = Membership.objects.get(user=self.user, company=self.company)
        membership.role = Membership.Role.VIEWER
        membership.save(update_fields=["role"])
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("api:stock-movements"), {},
            content_type="application/json", HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(response.status_code, 403)
