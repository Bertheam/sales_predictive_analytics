from django import forms
from django.contrib.auth import password_validation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import Company, Membership


class CompanyOnboardingForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "phone", "email", "city")
        labels = {
            "name": "Nom du dépôt",
            "phone": "Téléphone professionnel",
            "email": "E-mail professionnel",
            "city": "Ville",
        }
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": True, "placeholder": "Ex. Dépôt Horizon"}),
            "phone": forms.TextInput(attrs={"placeholder": "+223 70 00 00 00"}),
            "email": forms.EmailInput(attrs={"placeholder": "contact@depot.com"}),
            "city": forms.TextInput(attrs={"placeholder": "Bamako"}),
        }


class CompanyEditForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "phone", "email", "city", "currency", "timezone")
        labels = {
            "name": "Nom du dépôt", "phone": "Téléphone", "email": "E-mail",
            "city": "Ville", "currency": "Devise", "timezone": "Fuseau horaire",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "currency": forms.TextInput(attrs={"class": "form-control", "maxlength": 3}),
            "timezone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()

    def clean_timezone(self):
        value = self.cleaned_data["timezone"].strip()
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise forms.ValidationError(
                "Saisissez un fuseau horaire valide, par exemple Africa/Bamako."
            ) from exc
        return value


class StyledTeamForm(forms.Form):
    def apply_style(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class InvitationForm(StyledTeamForm):
    email = forms.EmailField(label="Adresse e-mail")
    role = forms.ChoiceField(label="Rôle", choices=())

    def __init__(self, *args, can_invite_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (Membership.Role.ANALYST, "Analyste"),
            (Membership.Role.VIEWER, "Consultation"),
        ]
        if can_invite_admin:
            choices.insert(0, (Membership.Role.ADMIN, "Administrateur"))
        self.fields["role"].choices = choices
        self.apply_style()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class MemberRoleForm(StyledTeamForm):
    role = forms.ChoiceField(label="Nouveau rôle", choices=())

    def __init__(self, *args, can_assign_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (Membership.Role.ANALYST, "Analyste"),
            (Membership.Role.VIEWER, "Consultation"),
        ]
        if can_assign_admin:
            choices.insert(0, (Membership.Role.ADMIN, "Administrateur"))
        self.fields["role"].choices = choices
        self.apply_style()


class InvitationAcceptanceForm(StyledTeamForm):
    full_name = forms.CharField(label="Nom complet", max_length=180)
    password1 = forms.CharField(
        label="Mot de passe", widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Confirmation du mot de passe", widget=forms.PasswordInput
    )

    def __init__(self, *args, email="", **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email
        self.apply_style()

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        if password and password != cleaned.get("password2"):
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        if password:
            candidate = type("Candidate", (), {
                "email": self.email,
                "full_name": cleaned.get("full_name", ""),
                "username": self.email,
            })()
            try:
                password_validation.validate_password(password, candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned
