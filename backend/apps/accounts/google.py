from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from firebase_admin import auth
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.firebase import firebase_app
from apps.core.models import record_audit

from .models import User
from .views import AuthThrottle


class GoogleTokenSerializer(serializers.Serializer):
    id_token = serializers.CharField(max_length=10000, trim_whitespace=False)


class GoogleLoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthThrottle,)
    link_account = False

    def post(self, request):
        if not settings.FIREBASE_PROJECT_ID:
            return Response({"detail": "Google sign-in is not configured yet."}, status=503)
        serializer = GoogleTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            claims = auth.verify_id_token(
                serializer.validated_data["id_token"], app=firebase_app(), check_revoked=True
            )
        except Exception:
            return Response(
                {"detail": "Unable to verify Google sign-in. Please try again."}, status=401
            )
        email = str(claims.get("email", "")).lower()
        uid = claims.get("uid") or claims.get("sub")
        if (
            not uid
            or not email
            or not claims.get("email_verified")
            or claims.get("firebase", {}).get("sign_in_provider") != "google.com"
        ):
            return Response({"detail": "A verified Google account is required."}, status=401)
        try:
            with transaction.atomic():
                if self.link_account:
                    user = User.objects.select_for_update().get(pk=request.user.pk)
                    if user.email.lower() != email or (
                        user.firebase_uid and user.firebase_uid != uid
                    ):
                        return Response(
                            {"detail": "Use the Google account matching your account email."},
                            status=400,
                        )
                    user.firebase_uid = uid
                else:
                    user = User.objects.select_for_update().filter(firebase_uid=uid).first()
                    if not user:
                        if User.objects.filter(email__iexact=email).exists():
                            return Response(
                                {
                                    "detail": "Log in with your password first, then link Google in Account settings."
                                },
                                status=409,
                            )
                        user = User.objects.create_user(
                            email=email,
                            name=str(claims.get("name", ""))[:180] or email.split("@")[0],
                            firebase_uid=uid,
                        )
                if not user.is_active or user.account_status in (
                    User.AccountStatus.SUSPENDED,
                    User.AccountStatus.DEACTIVATED,
                ):
                    return Response({"detail": "This account is not available."}, status=403)
                user.email_verified_at = user.email_verified_at or timezone.now()
                user.account_status = User.AccountStatus.ACTIVE
                user.save(update_fields=["firebase_uid", "email_verified_at", "account_status"])
                record_audit(
                    actor=user,
                    action="auth.google_link" if self.link_account else "auth.google_login",
                    target=user,
                    request=request,
                )
        except IntegrityError:
            return Response(
                {"detail": "This Google account is already linked. Please sign in again."},
                status=409,
            )
        if self.link_account:
            return Response({"detail": "Google account linked. You can now sign in with Google."})
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class GoogleLinkView(GoogleLoginView):
    permission_classes = (permissions.IsAuthenticated,)
    link_account = True
