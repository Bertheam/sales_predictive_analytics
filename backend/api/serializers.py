from rest_framework import serializers

from companies.models import Company, Membership


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "code", "name", "city", "currency", "timezone", "status")


class MembershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "company", "role", "role_label", "status", "joined_at")
