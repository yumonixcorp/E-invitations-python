import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTP


class OTPCooldown(Exception):
    def __init__(self, seconds_left):
        self.seconds_left = seconds_left
        super().__init__(f"Please wait {seconds_left}s before requesting another OTP.")


def normalize_email(email):
    return (email or "").strip().lower()


def send_otp_email(email, purpose="signup"):
    last = OTP.objects.filter(email=email, purpose=purpose).first()
    if last:
        elapsed = (timezone.now() - last.created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            raise OTPCooldown(int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1)

    OTP.objects.filter(email=email, is_used=False, purpose=purpose).update(is_used=True)
    code = OTP.generate_otp()
    OTP.objects.create(email=email, code=code, purpose=purpose)

    send_mail(
        "Your Verification Code",
        f"Unga OTP: {code}\n{settings.OTP_VALIDITY_MINUTES} minutes ku valid.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
    return code


def verify_otp(email, code, purpose):
    """Check the latest OTP for this email/purpose. Consumes it on success.

    Only the most recent code is considered, and each wrong guess counts
    toward OTP_MAX_ATTEMPTS, so codes can't be brute-forced.
    """
    otp = OTP.objects.filter(email=email, purpose=purpose, is_used=False).first()
    if not otp or not otp.is_valid():
        return False
    if not secrets.compare_digest(otp.code, str(code or "").strip()):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        return False
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return True


def purge_old_otps(days=1):
    OTP.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
