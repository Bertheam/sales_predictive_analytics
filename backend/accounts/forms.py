from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User
from .identifiers import normalize_phone


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="E-mail ou téléphone",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "placeholder": "nom@exemple.com ou +223…",
            }
        ),
    )


class RegistrationForm(UserCreationForm):
    consent = forms.BooleanField(
        label="J’accepte les conditions d’utilisation et la politique de confidentialité."
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "password1", "password2")
        labels = {"full_name": "Nom complet", "email": "Adresse e-mail"}

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "phone")
        labels = {
            "full_name": "Nom complet",
            "email": "Adresse e-mail",
            "phone": "Numéro de téléphone",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower() or None
        if email and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if phone and User.objects.exclude(pk=self.instance.pk).filter(phone=phone).exists():
            raise forms.ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return phone

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("email") and not cleaned.get("phone"):
            raise forms.ValidationError(
                "Conservez au moins une adresse e-mail ou un numéro de téléphone."
            )
        return cleaned
