from django.test import TestCase
from django.urls import reverse

from .models import User


class RegistrationTests(TestCase):
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
