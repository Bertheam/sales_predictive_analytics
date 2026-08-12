from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .identifiers import normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email=None, password=None, **extra_fields):
        phone = normalize_phone(extra_fields.pop("phone", None))
        if not email and not phone:
            raise ValueError("Une adresse e-mail ou un numéro de téléphone est obligatoire.")
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Une adresse e-mail est obligatoire pour le superutilisateur.")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Le superutilisateur doit avoir les droits staff et superutilisateur.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("adresse e-mail", unique=True, null=True, blank=True)
    phone = models.CharField(
        "numéro de téléphone", max_length=20, unique=True, null=True, blank=True
    )
    full_name = models.CharField("nom complet", max_length=180)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        ordering = ["full_name", "email", "phone"]

    @property
    def login_identifier(self):
        return self.email or self.phone or ""

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email) if self.email else None
        self.phone = normalize_phone(self.phone)
        if not self.email and not self.phone:
            raise ValidationError(
                "Une adresse e-mail ou un numéro de téléphone est obligatoire."
            )

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email) if self.email else None
        self.phone = normalize_phone(self.phone)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.login_identifier
