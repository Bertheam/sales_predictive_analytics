from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError
from django.db.models import Q

from .identifiers import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate a NexaStock account with either e-mail or phone."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        identifier = username or kwargs.get(UserModel.USERNAME_FIELD)
        if not identifier or password is None:
            return None
        identifier = identifier.strip()
        query = Q(email__iexact=identifier)
        try:
            phone = normalize_phone(identifier)
        except ValidationError:
            phone = None
        if phone:
            query |= Q(phone=phone)
        user = UserModel._default_manager.filter(query).first()
        if user is None:
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
