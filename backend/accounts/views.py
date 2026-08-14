from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import EmailAuthenticationForm, ProfileForm, RegistrationForm
from audit.models import AuditLog
from audit.services import record_audit


class RateLimitedLoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm

    def _client_address(self):
        if settings.RATE_LIMIT_TRUST_X_FORWARDED_FOR:
            forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return self.request.META.get("REMOTE_ADDR", "unknown")

    def _cache_key(self):
        digest = sha256(self._client_address().encode("utf-8")).hexdigest()
        return f"auth:web-login:{digest}"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and cache.get(self._cache_key(), 0) >= settings.WEB_LOGIN_MAX_ATTEMPTS:
            form = self.authentication_form(request=request)
            response = render(
                request,
                self.template_name,
                {
                    "form": form,
                    "next": request.POST.get("next", ""),
                    "rate_limit_error": (
                        "Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer."
                    ),
                },
                status=429,
            )
            response["Retry-After"] = str(settings.WEB_LOGIN_WINDOW_SECONDS)
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._cache_key()
        if not cache.add(key, 1, timeout=settings.WEB_LOGIN_WINDOW_SECONDS):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=settings.WEB_LOGIN_WINDOW_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key())
        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("companies:onboarding")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    previous = {
        "full_name": request.user.full_name,
        "email": request.user.email,
        "phone": request.user.phone,
    }
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(
            request,
            action=AuditLog.Action.UPDATE,
            resource_type="user_profile",
            resource_id=request.user.pk,
            description="Modification du profil utilisateur.",
            metadata={
                "changed_fields": [
                    field for field in ("full_name", "email", "phone")
                    if previous[field] != form.cleaned_data[field]
                ]
            },
        )
        messages.success(request, "Votre profil a été mis à jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
