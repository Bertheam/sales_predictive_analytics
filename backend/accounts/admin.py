from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil", {"fields": ("full_name",)}),
        ("Autorisations", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),)
    search_fields = ("email", "full_name")
