from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from rest_framework import generics, permissions, status, throttling
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.models import record_audit

from .models import EmailVerificationToken, User
from .serializers import (
    AccountTokenRefreshSerializer,
    LoginTokenSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)


class AuthThrottle(throttling.AnonRateThrottle):
    scope = "auth"


class LoginView(TokenObtainPairView):
    serializer_class = LoginTokenSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            user = User.objects.filter(email__iexact=request.data.get("email", "")).first()
            record_audit(actor=user, action="auth.login", target=user, request=request)
        return response


class RegisterView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)

    @transaction.atomic
    def perform_create(self, serializer):
        user = serializer.save()
        verification, raw_token = EmailVerificationToken.issue(user)
        verify_path = reverse("verify-email")
        verify_url = self.request.build_absolute_uri(f"{verify_path}?token={raw_token}")
        send_mail(
            "Verify your ScanToForms email",
            f"Verify your account: {verify_url}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        record_audit(actor=user, action="auth.register", target=user, request=self.request)
        self.verification_expires_at = verification.expires_at


class VerifyEmailView(generics.GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)

    def _verify(self, request, raw_token):
        token = EmailVerificationToken.consume(raw_token)
        if not token:
            return Response({"detail": "Invalid or expired verification token."}, status=status.HTTP_400_BAD_REQUEST)
        user = token.user
        from django.utils import timezone

        if not user.is_active or user.account_status in (User.AccountStatus.SUSPENDED, User.AccountStatus.DEACTIVATED):
            return Response({"detail": "This account is not available."}, status=status.HTTP_403_FORBIDDEN)
        user.email_verified_at = timezone.now()
        user.account_status = User.AccountStatus.ACTIVE
        user.save(update_fields=["email_verified_at", "account_status"])
        record_audit(actor=user, action="auth.email_verified", target=user, request=request)
        return Response({"detail": "Email verified."})

    def get(self, request):
        return self._verify(request, request.query_params.get("token", ""))

    def post(self, request):
        return self._verify(request, request.data.get("token", ""))


class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            if str(token.get("user_id")) != str(request.user.pk):
                return Response(status=status.HTTP_403_FORBIDDEN)
            token.blacklist()
        except (ValueError, TokenError):
            return Response({"detail": "A valid refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        record_audit(actor=request.user, action="auth.logout", target=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user:
            data = serializer.token_for_user(user)
            reset_url = settings.FRONTEND_URL + f"/reset-password?uid={data['uid']}&token={data['token']}"
            send_mail("Reset your ScanToForms password", reset_url, settings.DEFAULT_FROM_EMAIL, [user.email])
            record_audit(actor=user, action="auth.password_reset_requested", target=user, request=request)
        return Response({"detail": "If that account exists, reset instructions have been sent."})


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_audit(actor=user, action="auth.password_reset_completed", target=user, request=request)
        return Response({"detail": "Password reset successful."})


class RefreshView(TokenRefreshView):
    serializer_class = AccountTokenRefreshSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)
