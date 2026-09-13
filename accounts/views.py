from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from billing.quota import get_subscription, quota_summary

from .utils import OTPCooldown, normalize_email, send_otp_email, verify_otp

User = get_user_model()


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _clean_email(request):
    email = normalize_email(request.data.get("email"))
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


class _OTPRequestBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"
    purpose = None

    def check_email(self, email):
        raise NotImplementedError

    def post(self, request):
        email = _clean_email(request)
        if not email:
            return Response({"error": "Enter a valid email address."}, status=400)
        error = self.check_email(email)
        if error:
            return error
        try:
            send_otp_email(email, purpose=self.purpose)
        except OTPCooldown as exc:
            return Response({"error": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except Exception:
            return Response({"error": "Could not send the OTP email. Try again later."}, status=502)
        return Response({"message": "OTP sent."})


class SignupRequestView(_OTPRequestBase):
    purpose = "signup"

    def check_email(self, email):
        if User.objects.filter(email=email, is_email_verified=True).exists():
            return Response({"error": "Already registered. Please log in."}, status=400)
        return None


class LoginRequestView(_OTPRequestBase):
    purpose = "login"

    def check_email(self, email):
        if not User.objects.filter(email=email, is_email_verified=True).exists():
            return Response({"error": "No account found. Please sign up."}, status=404)
        return None


class SignupVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        email = _clean_email(request)
        password = request.data.get("password")
        if not email:
            return Response({"error": "Enter a valid email address."}, status=400)
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                return Response({"error": " ".join(exc.messages)}, status=400)
        if not verify_otp(email, request.data.get("otp"), "signup"):
            return Response({"error": "Invalid/expired OTP."}, status=400)

        with transaction.atomic():
            user, _ = User.objects.get_or_create(email=email, defaults={"username": email})
            if password:
                user.set_password(password)
            elif not user.has_usable_password():
                user.set_unusable_password()
            user.is_email_verified = True
            user.save()
            get_subscription(user)
        return Response(_tokens_for(user))


class LoginVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        email = _clean_email(request)
        if not email or not verify_otp(email, request.data.get("otp"), "login"):
            return Response({"error": "Invalid/expired OTP."}, status=400)
        user = User.objects.filter(email=email, is_email_verified=True, is_active=True).first()
        if not user:
            return Response({"error": "No account found."}, status=404)
        return Response(_tokens_for(user))


class MeView(APIView):
    def get(self, request):
        return Response({"email": request.user.email, "quota": quota_summary(request.user)})
