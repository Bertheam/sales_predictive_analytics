from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify

from .forms import CompanyEditForm, CompanyOnboardingForm, InvitationAcceptanceForm, InvitationForm, MemberRoleForm
from .models import Company, CompanyInvitation, Membership
from .permissions import company_roles_required
from .services import (
    accept_company_invitation,
    bootstrap_company_references,
    can_manage_member,
    company_accesses_for,
    company_management_accesses_for,
    create_or_refresh_invitation,
    hash_invitation_token,
    set_member_suspended,
    team_overview,
    update_member_role,
)
from audit.models import AuditLog
from audit.services import record_audit


def _unique_company_code(name):
    root = slugify(name)[:60] or "depot"
    while True:
        code = f"{root}-{uuid4().hex[:6]}"
        if not Company.objects.filter(code=code).exists():
            return code


@login_required
def onboarding(request):
    form = CompanyOnboardingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            company = form.save(commit=False)
            company.code = _unique_company_code(company.name)
            company.save()
            Membership.objects.create(
                company=company,
                user=request.user,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
                joined_at=timezone.now(),
            )
            bootstrap_company_references(company.id)
        record_audit(
            request,
            action=AuditLog.Action.CREATE,
            resource_type="company",
            resource_id=company.id,
            company=company,
            description=f"Création du dépôt {company.name}.",
        )
        request.session["active_company_id"] = str(company.pk)
        messages.success(request, f"Bienvenue dans {company.name}. Votre espace est prêt.")
        return redirect("dashboard:home")
    return render(request, "companies/onboarding.html", {"form": form})


@login_required
def select_company(request):
    memberships = company_accesses_for(request.user)
    if request.method == "POST":
        try:
            company_id = request.POST.get("company_id")
            membership = next(
                (access for access in memberships if str(access.company_id) == company_id),
                None,
            )
        except (ValidationError, ValueError):
            membership = None
        if membership:
            request.session["active_company_id"] = str(membership.company_id)
            record_audit(
                request,
                action=AuditLog.Action.SELECT_COMPANY,
                resource_type="company",
                resource_id=membership.company_id,
                company=membership.company,
                description=f"Sélection du dépôt {membership.company.name}.",
            )
            messages.success(request, f"Vous travaillez maintenant sur {membership.company.name}.")
            next_url = request.POST.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("dashboard:home")
        messages.error(request, "Vous n’avez pas accès à ce dépôt.")
    return render(request, "companies/select.html", {"memberships": memberships})


@login_required
def company_list(request):
    accesses = company_management_accesses_for(request.user)
    return render(request, "companies/company_list.html", {"accesses": accesses})


def _manageable_company(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.user.is_superuser:
        return company
    membership = Membership.objects.filter(
        company=company,
        user=request.user,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
    ).first()
    return company if membership else None


@login_required
def company_edit(request, company_id):
    company = _manageable_company(request, company_id)
    if company is None:
        return HttpResponseForbidden("Seul le propriétaire peut modifier ce dépôt.")
    form = CompanyEditForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(
            request, action=AuditLog.Action.UPDATE, resource_type="company",
            resource_id=company.id, company=company,
            description=f"Modification des informations du dépôt {company.name}.",
        )
        messages.success(request, f"Les informations de {company.name} ont été mises à jour.")
        return redirect("companies:list")
    return render(request, "companies/company_form.html", {"form": form, "company": company})


@login_required
def company_status(request, company_id):
    if request.method != "POST":
        raise Http404
    company = _manageable_company(request, company_id)
    if company is None:
        return HttpResponseForbidden("Seul le propriétaire peut archiver ce dépôt.")
    restoring = request.POST.get("action") == "restore"
    company.status = Company.Status.ACTIVE if restoring else Company.Status.ARCHIVED
    company.save(update_fields=["status", "updated_at"])
    record_audit(
        request,
        action=AuditLog.Action.UPDATE if restoring else AuditLog.Action.DELETE,
        resource_type="company", resource_id=company.id, company=company,
        description=(f"Restauration du dépôt {company.name}." if restoring else f"Archivage logique du dépôt {company.name}."),
        metadata={"logical_deletion": not restoring},
    )
    if not restoring and request.session.get("active_company_id") == str(company.id):
        request.session.pop("active_company_id", None)
    messages.success(request, f"Dépôt {'restauré' if restoring else 'archivé'} avec succès.")
    return redirect("companies:list")


TEAM_MANAGEMENT_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


@company_roles_required(*TEAM_MANAGEMENT_ROLES)
def team(request):
    members, invitations, summary = team_overview(request.company)
    platform_admin = getattr(request, "is_platform_admin", False)
    for member in members:
        member.can_be_managed = can_manage_member(
            request.membership, member, platform_admin=platform_admin
        )
    can_invite_admin = platform_admin or request.membership.role == Membership.Role.OWNER
    return render(request, "companies/team.html", {
        "members": members,
        "invitations": invitations,
        "summary": summary,
        "invitation_form": InvitationForm(can_invite_admin=can_invite_admin),
        "can_invite_admin": can_invite_admin,
    })


@company_roles_required(*TEAM_MANAGEMENT_ROLES)
def invite_member(request):
    if request.method != "POST":
        raise Http404
    platform_admin = getattr(request, "is_platform_admin", False)
    can_invite_admin = platform_admin or request.membership.role == Membership.Role.OWNER
    form = InvitationForm(request.POST, can_invite_admin=can_invite_admin)
    if not form.is_valid():
        members, invitations, summary = team_overview(request.company)
        for member in members:
            member.can_be_managed = can_manage_member(
                request.membership, member, platform_admin=platform_admin
            )
        return render(request, "companies/team.html", {
            "members": members, "invitations": invitations, "summary": summary,
            "invitation_form": form, "can_invite_admin": can_invite_admin,
        }, status=400)
    try:
        invitation, raw_token = create_or_refresh_invitation(
            company=request.company,
            email=form.cleaned_data["email"],
            role=form.cleaned_data["role"],
            invited_by=request.user,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("companies:team")
    accept_url = request.build_absolute_uri(
        reverse("companies:invitation-accept", args=[raw_token])
    )
    sent = send_mail(
        subject=f"Invitation à rejoindre {request.company.name} sur NexaStock",
        message=(
            f"Vous êtes invité(e) à rejoindre {request.company.name} avec le rôle "
            f"{invitation.get_role_display()}.\n\n"
            f"Acceptez l’invitation avant le {invitation.expires_at:%d/%m/%Y} :\n"
            f"{accept_url}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=True,
    )
    record_audit(request, action=AuditLog.Action.CREATE, resource_type="company_invitation", resource_id=invitation.id, description=f"Invitation de {invitation.email} comme {invitation.get_role_display()}.", metadata={"email": invitation.email, "role": invitation.role, "email_sent": bool(sent)})
    if sent:
        messages.success(request, f"Invitation envoyée à {invitation.email}.")
    else:
        messages.warning(request, "Invitation créée, mais l’e-mail n’a pas pu être envoyé. Vérifiez la configuration SMTP.")
    return redirect("companies:team")


@company_roles_required(*TEAM_MANAGEMENT_ROLES)
def revoke_invitation(request, invitation_id):
    if request.method != "POST":
        raise Http404
    invitation = get_object_or_404(
        CompanyInvitation,
        pk=invitation_id,
        company=request.company,
        status=CompanyInvitation.Status.PENDING,
    )
    if invitation.role == Membership.Role.ADMIN and not (
        getattr(request, "is_platform_admin", False)
        or request.membership.role == Membership.Role.OWNER
    ):
        return HttpResponseForbidden("Seul le propriétaire peut révoquer cette invitation.")
    invitation.status = CompanyInvitation.Status.REVOKED
    invitation.save(update_fields=["status", "updated_at"])
    record_audit(request, action=AuditLog.Action.DELETE, resource_type="company_invitation", resource_id=invitation.id, description=f"Révocation de l’invitation envoyée à {invitation.email}.", metadata={"email": invitation.email, "role": invitation.role})
    messages.success(request, "Invitation révoquée.")
    return redirect("companies:team")


@company_roles_required(*TEAM_MANAGEMENT_ROLES)
def member_edit(request, membership_id):
    target = get_object_or_404(
        Membership.objects.select_related("user"),
        pk=membership_id,
        company=request.company,
    )
    platform_admin = getattr(request, "is_platform_admin", False)
    if not can_manage_member(request.membership, target, platform_admin=platform_admin):
        return HttpResponseForbidden("Vous ne pouvez pas modifier ce membre.")
    can_assign_admin = platform_admin or request.membership.role == Membership.Role.OWNER
    form = MemberRoleForm(
        request.POST or None,
        can_assign_admin=can_assign_admin,
        initial={"role": target.role},
    )
    if request.method == "POST" and form.is_valid():
        previous_role = target.role
        try:
            update_member_role(
                actor_membership=request.membership,
                target=target,
                role=form.cleaned_data["role"],
                platform_admin=platform_admin,
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            record_audit(request, action=AuditLog.Action.UPDATE, resource_type="company_membership", resource_id=target.id, description=f"Modification du rôle de {target.user.email} : {previous_role} → {target.role}.", metadata={"user_id": target.user_id, "previous_role": previous_role, "new_role": target.role})
            messages.success(request, f"Le rôle de {target.user.full_name or target.user.email} a été mis à jour.")
            return redirect("companies:team")
    return render(request, "companies/member_edit.html", {"form": form, "member": target})


@company_roles_required(*TEAM_MANAGEMENT_ROLES)
def member_access(request, membership_id):
    if request.method != "POST":
        raise Http404
    target = get_object_or_404(
        Membership.objects.select_related("user"),
        pk=membership_id,
        company=request.company,
    )
    suspended = request.POST.get("action") != "restore"
    try:
        set_member_suspended(
            actor_membership=request.membership,
            target=target,
            suspended=suspended,
            platform_admin=getattr(request, "is_platform_admin", False),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("companies:team")
    record_audit(request, action=AuditLog.Action.DELETE if suspended else AuditLog.Action.UPDATE, resource_type="company_membership", resource_id=target.id, description=(f"Suspension de l’accès de {target.user.email}." if suspended else f"Réactivation de l’accès de {target.user.email}."), metadata={"user_id": target.user_id, "status": target.status})
    messages.success(request, "Accès suspendu." if suspended else "Accès réactivé.")
    return redirect("companies:team")


def accept_invitation(request, token):
    invitation = get_object_or_404(
        CompanyInvitation.objects.select_related("company"),
        token_hash=hash_invitation_token(token),
    )
    if invitation.status != CompanyInvitation.Status.PENDING or invitation.is_expired:
        return render(request, "companies/invitation_accept.html", {
            "invitation": invitation, "unavailable": True,
        }, status=410)
    existing_user = get_user_model().objects.filter(
        email__iexact=invitation.email
    ).first()
    if request.user.is_authenticated:
        if request.user.email.lower() != invitation.email.lower():
            return render(request, "companies/invitation_accept.html", {
                "invitation": invitation, "email_mismatch": True,
            }, status=403)
        try:
            membership = accept_company_invitation(invitation, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("companies:select")
        request.session["active_company_id"] = str(membership.company_id)
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="company_membership", resource_id=membership.id, company=membership.company, description=f"Acceptation de l’invitation à rejoindre {membership.company.name}.", metadata={"role": membership.role})
        messages.success(request, f"Vous avez rejoint {membership.company.name}.")
        return redirect("dashboard:home")
    if existing_user:
        login_url = f"{reverse('accounts:login')}?next={request.path}"
        return redirect(login_url)
    form = InvitationAcceptanceForm(
        request.POST or None, email=invitation.email
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                email=invitation.email,
                full_name=form.cleaned_data["full_name"],
                password=form.cleaned_data["password1"],
            )
            membership = accept_company_invitation(invitation, user)
        login(request, user)
        request.session["active_company_id"] = str(membership.company_id)
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="company_membership", resource_id=membership.id, company=membership.company, description=f"Création du compte et acceptation de l’invitation à rejoindre {membership.company.name}.", metadata={"role": membership.role})
        messages.success(request, f"Bienvenue dans {membership.company.name}.")
        return redirect("dashboard:home")
    return render(request, "companies/invitation_accept.html", {
        "invitation": invitation, "form": form,
    })
