from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email", "phone")
    list_display = ("email", "phone", "full_name", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "phone", "password")}),
        ("Profil", {"fields": ("full_name",)}),
        ("Autorisations", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "phone", "full_name", "password1", "password2")}),)
    search_fields = ("email", "phone", "full_name")
