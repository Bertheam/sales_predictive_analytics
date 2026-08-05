from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegistrationForm
from audit.models import AuditLog
from audit.services import record_audit


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
    previous = {"full_name": request.user.full_name, "email": request.user.email}
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
                    field for field in ("full_name", "email")
                    if previous[field] != form.cleaned_data[field]
                ]
            },
        )
        messages.success(request, "Votre profil a été mis à jour.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
