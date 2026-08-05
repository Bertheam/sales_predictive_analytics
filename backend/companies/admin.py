from django.contrib import admin

from .models import Company, CompanyInvitation, Membership


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("name", "code", "email", "phone")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("user__email", "user__full_name", "company__name")


@admin.register(CompanyInvitation)
class CompanyInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "company", "role", "status", "expires_at", "created_at")
    list_filter = ("role", "status")
    search_fields = ("email", "company__name")
    readonly_fields = (
        "token_hash", "invited_by", "accepted_by", "accepted_at",
        "created_at", "updated_at",
    )
