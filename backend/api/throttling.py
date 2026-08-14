from rest_framework.permissions import SAFE_METHODS
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class DynamicRateMixin:
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)


class LoginRateThrottle(DynamicRateMixin, SimpleRateThrottle):
    """Limit authentication attempts by client address, authenticated or not."""

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class SensitiveWriteRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Protect API mutations without limiting normal dashboard consultation."""

    scope = "sensitive_write"

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)
