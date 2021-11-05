from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.db.models import Q


class UsernameOrEmailBackend(BaseBackend):
    """Backend to allow authentication with either username or email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(Q(username=username) | Q(email=username)) 
        except User.DoesNotExist:
            return None

        if getattr(user, 'is_active') and user.check_password(password):
            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None