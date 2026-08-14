from rest_framework.permissions import BasePermission

from companies.models import Membership


MANAGEMENT_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
FORECAST_ROLES = MANAGEMENT_ROLES | {Membership.Role.ANALYST}


class CompanyRolePermission(BasePermission):
    write_roles = MANAGEMENT_ROLES

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        membership = getattr(request, "membership", None)
        return bool(membership and membership.role in getattr(view, "write_roles", self.write_roles))
