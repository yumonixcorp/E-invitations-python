import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import OTP, User


def last_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class OTPAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_signup_then_login(self):
        resp = self.client.post("/api/auth/signup/request-otp/", {"email": "Saran@Example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/api/auth/signup/verify-otp/", {"email": "saran@example.com", "otp": last_code()}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        user = User.objects.get(email="saran@example.com")
        self.assertTrue(user.is_email_verified)
        self.assertTrue(hasattr(user, "subscription"))

        OTP.objects.update(created_at="2000-01-01T00:00:00Z")  # skip resend cooldown
        resp = self.client.post("/api/auth/login/request-otp/", {"email": "saran@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/api/auth/login/verify-otp/", {"email": "saran@example.com", "otp": last_code()}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

        me = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        self.assertEqual(me.data["quota"]["plan"], "free")

    def test_login_unknown_email(self):
        resp = self.client.post("/api/auth/login/request-otp/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_otp_is_single_use(self):
        self.client.post("/api/auth/signup/request-otp/", {"email": "a@example.com"}, format="json")
        code = last_code()
        payload = {"email": "a@example.com", "otp": code}
        self.assertEqual(self.client.post("/api/auth/signup/verify-otp/", payload, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/signup/verify-otp/", payload, format="json").status_code, 400)

    def test_wrong_guesses_lock_the_code(self):
        self.client.post("/api/auth/signup/request-otp/", {"email": "b@example.com"}, format="json")
        code = last_code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.client.post("/api/auth/signup/verify-otp/", {"email": "b@example.com", "otp": wrong}, format="json")
        resp = self.client.post("/api/auth/signup/verify-otp/", {"email": "b@example.com", "otp": code}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_resend_cooldown(self):
        self.client.post("/api/auth/signup/request-otp/", {"email": "c@example.com"}, format="json")
        resp = self.client.post("/api/auth/signup/request-otp/", {"email": "c@example.com"}, format="json")
        self.assertEqual(resp.status_code, 429)
