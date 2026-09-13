import hashlib
import hmac
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User

from .models import Payment, Subscription
from .quota import can_create_invitation, get_subscription, reserve_invitation_slot


class QuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u@example.com", email="u@example.com", is_email_verified=True)

    def test_free_plan_allows_one_per_month(self):
        self.assertTrue(reserve_invitation_slot(self.user))
        self.assertFalse(reserve_invitation_slot(self.user))

    def test_counter_resets_in_new_month(self):
        reserve_invitation_slot(self.user)
        Subscription.objects.filter(user=self.user).update(last_reset_date=date.today() - timedelta(days=40))
        self.assertTrue(can_create_invitation(self.user))

    def test_expired_paid_plan_falls_back_to_free(self):
        Subscription.objects.create(
            user=self.user, plan="basic", invitations_used_this_month=3,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(get_subscription(self.user).plan, "free")
        self.assertFalse(can_create_invitation(self.user))


@override_settings(RAZORPAY_KEY_ID="rzp_test_key", RAZORPAY_KEY_SECRET="secret123")
class PaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="p@example.com", email="p@example.com", is_email_verified=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_verified_payment_activates_plan(self):
        Payment.objects.create(user=self.user, plan="basic", amount_paise=19900, razorpay_order_id="order_1")
        signature = hmac.new(b"secret123", b"order_1|pay_1", hashlib.sha256).hexdigest()
        resp = self.client.post("/api/billing/verify/", {
            "razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1", "razorpay_signature": signature,
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["quota"]["plan"], "basic")
        self.assertEqual(Payment.objects.get().status, "paid")

    def test_bad_signature_rejected(self):
        Payment.objects.create(user=self.user, plan="pro", amount_paise=49900, razorpay_order_id="order_2")
        resp = self.client.post("/api/billing/verify/", {
            "razorpay_order_id": "order_2", "razorpay_payment_id": "pay_2", "razorpay_signature": "forged",
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(get_subscription(self.user).plan, "free")

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_order_requires_configuration(self):
        resp = self.client.post("/api/billing/order/", {"plan": "basic"}, format="json")
        self.assertEqual(resp.status_code, 503)
