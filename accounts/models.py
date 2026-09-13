import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)


class OTP(models.Model):
    PURPOSE_CHOICES = [("signup", "Signup"), ("login", "Login")]

    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def generate_otp():
        return f"{secrets.randbelow(900000) + 100000}"

    def is_valid(self):
        expires_at = self.created_at + timedelta(minutes=settings.OTP_VALIDITY_MINUTES)
        return (
            not self.is_used
            and self.attempts < settings.OTP_MAX_ATTEMPTS
            and timezone.now() <= expires_at
        )

    def __str__(self):
        return f"{self.email} ({self.purpose})"
