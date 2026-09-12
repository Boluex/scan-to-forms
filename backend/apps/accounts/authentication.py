from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import User


class ActiveAccountJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.account_status in (User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED):
            raise AuthenticationFailed("This account is not available.", code="account_unavailable")
        return user

