import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

from django.test import RequestFactory, TestCase, override_settings

from accounts.models import User
from .models import Company
from .streamlit_access import build_streamlit_access_url


@override_settings(
    STREAMLIT_PUBLIC_URL="https://lab.example.test",
    STREAMLIT_SIGNING_KEY="shared-test-secret",
    STREAMLIT_ACCESS_TOKEN_TTL_SECONDS=300,
)
class StreamlitAccessLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner-lab@example.test",
            password="safe-test-password",
        )
        self.company = Company.objects.create(code="lab", name="Dépôt laboratoire")
        self.request = RequestFactory().get("/")
        self.request.user = self.user
        self.request.company = self.company

    def test_link_contains_a_valid_tenant_bound_signature(self):
        url = build_streamlit_access_url(self.request)
        token = parse_qs(urlparse(url).query)["access"][0]
        encoded_payload, supplied_signature = token.split(".", 1)
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(
                b"shared-test-secret",
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii").rstrip("=")
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )

        self.assertTrue(hmac.compare_digest(supplied_signature, expected_signature))
        self.assertEqual(payload["company_id"], str(self.company.pk))
        self.assertEqual(payload["user_id"], str(self.user.pk))

    @override_settings(STREAMLIT_SIGNING_KEY="")
    def test_link_is_hidden_when_signature_is_not_configured(self):
        self.assertEqual(build_streamlit_access_url(self.request), "")
