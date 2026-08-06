import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.conf import settings


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def build_streamlit_access_url(request) -> str:
    """Build a short-lived, tenant-bound link to the technical laboratory."""
    company = getattr(request, "company", None)
    if not request.user.is_authenticated or company is None:
        return ""

    base_url = settings.STREAMLIT_PUBLIC_URL.rstrip("/")
    signing_key = settings.STREAMLIT_SIGNING_KEY
    if not base_url or not signing_key:
        return ""

    payload = {
        "company_id": str(company.pk),
        "user_id": str(request.user.pk),
        "exp": int(time.time()) + settings.STREAMLIT_ACCESS_TOKEN_TTL_SECONDS,
    }
    encoded_payload = _encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _encode(
        hmac.new(
            signing_key.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{base_url}/?{urlencode({'access': f'{encoded_payload}.{signature}'})}"
