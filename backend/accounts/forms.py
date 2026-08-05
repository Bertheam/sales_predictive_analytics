from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Adresse e-mail", widget=forms.EmailInput(attrs={"autofocus": True}))


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
        fields = ("full_name", "email")
        labels = {"full_name": "Nom complet", "email": "Adresse e-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email
