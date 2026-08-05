from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import Company, Membership


def company_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not getattr(request, "company", None):
            if request.user.is_superuser and Company.objects.filter(
                status=Company.Status.ACTIVE
            ).exists():
                return redirect("companies:select")
            if Membership.objects.filter(user=request.user, status=Membership.Status.ACTIVE).exists():
                return redirect("companies:select")
            messages.info(request, "Créez votre dépôt pour commencer.")
            return redirect("companies:onboarding")
        return view_func(request, *args, **kwargs)

    return wrapped


def company_roles_required(*allowed_roles):
    def decorator(view_func):
        @company_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.membership.role not in allowed_roles:
                return HttpResponseForbidden(
                    "Votre rôle ne permet pas d’effectuer cette opération."
                )
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
