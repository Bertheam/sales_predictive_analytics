from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from .models import User


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_registration_creates_user_and_starts_onboarding(self):
        response = self.client.post(reverse("accounts:register"), {
            "full_name": "Awa Traoré",
            "email": "AWA@example.com",
            "password1": "Test-password-2026!",
            "password2": "Test-password-2026!",
            "consent": "on",
        })
        self.assertRedirects(response, reverse("companies:onboarding"))
        self.assertTrue(User.objects.filter(email="awa@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_uses_email(self):
        User.objects.create_user(email="owner@example.com", password="A-secure-password-2026", full_name="Owner")
        response = self.client.post(reverse("accounts:login"), {
            "username": "owner@example.com",
            "password": "A-secure-password-2026",
        })
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)

    def test_phone_only_user_can_login_with_phone(self):
        user = User.objects.create_user(
            phone="+223 70 00 00 00",
            password="A-secure-password-2026",
            full_name="Gestionnaire sans e-mail",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "+22370000000",
                "password": "A-secure-password-2026",
            },
        )

        self.assertIsNone(user.email)
        self.assertEqual(user.phone, "+22370000000")
        self.assertRedirects(
            response, reverse("dashboard:home"), fetch_redirect_response=False
        )

    def test_user_with_email_and_phone_can_use_either_identifier(self):
        user = User.objects.create_user(
            email="manager@example.com",
            phone="00223 76 00 00 01",
            password="A-secure-password-2026",
            full_name="Gestionnaire polyvalent",
        )

        email_response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "MANAGER@example.com",
                "password": "A-secure-password-2026",
            },
        )
        self.assertEqual(email_response.status_code, 302)
        self.client.logout()

        phone_response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "+22376000001",
                "password": "A-secure-password-2026",
            },
        )

        self.assertEqual(user.phone, "+22376000001")
        self.assertRedirects(
            phone_response, reverse("dashboard:home"), fetch_redirect_response=False
        )

    @override_settings(WEB_LOGIN_MAX_ATTEMPTS=2, WEB_LOGIN_WINDOW_SECONDS=300)
    def test_web_login_is_temporarily_limited_after_repeated_failures(self):
        User.objects.create_user(
            email="limited@example.com",
            password="A-secure-password-2026",
            full_name="Compte limité",
        )
        payload = {"username": "limited@example.com", "password": "incorrect"}

        self.assertEqual(self.client.post(reverse("accounts:login"), payload).status_code, 200)
        self.assertEqual(self.client.post(reverse("accounts:login"), payload).status_code, 200)
        response = self.client.post(reverse("accounts:login"), payload)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "300")
        self.assertContains(response, "Trop de tentatives de connexion", status_code=429)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            password="A-secure-password-2026",
            full_name="Ancien nom",
        )
        self.client.force_login(self.user)

    def test_profile_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_user_can_update_profile(self):
        response = self.client.post(reverse("accounts:profile"), {
            "full_name": "Nouveau nom",
            "email": "NOUVEAU@example.com",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Nouveau nom")
        self.assertEqual(self.user.email, "nouveau@example.com")

    def test_profile_rejects_an_email_already_used(self):
        User.objects.create_user(
            email="existing@example.com",
            password="A-secure-password-2026",
            full_name="Autre compte",
        )
        response = self.client.post(reverse("accounts:profile"), {
            "full_name": "Nouveau nom",
            "email": "existing@example.com",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cette adresse e-mail est déjà utilisée.")
