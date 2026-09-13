import hashlib
import hmac
import time

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .quota import activate_plan, quota_summary

RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


def payments_enabled():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def verify_razorpay_signature(order_id, payment_id, signature):
    message = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


class PlansView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        plans = [{"id": key, **value} for key, value in settings.PLANS.items()]
        return Response({
            "plans": plans,
            "plan_days": settings.PAID_PLAN_DAYS,
            "payments_enabled": payments_enabled(),
        })


class CreateOrderView(APIView):
    def post(self, request):
        plan = request.data.get("plan")
        info = settings.PLANS.get(plan)
        if not info or not info["price_inr"]:
            return Response({"error": "Choose a paid plan."}, status=400)
        if not payments_enabled():
            return Response({"error": "Payments are not configured on this server."}, status=503)

        amount = info["price_inr"] * 100
        try:
            resp = requests.post(
                RAZORPAY_ORDERS_URL,
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                json={
                    "amount": amount,
                    "currency": "INR",
                    "receipt": f"u{request.user.id}-{plan}-{int(time.time())}",
                    "notes": {"user_id": str(request.user.id), "plan": plan},
                },
                timeout=20,
            )
            resp.raise_for_status()
        except requests.RequestException:
            return Response({"error": "Could not start the payment. Try again."}, status=502)

        order = resp.json()
        Payment.objects.create(
            user=request.user, plan=plan, amount_paise=amount, razorpay_order_id=order["id"]
        )
        return Response({
            "order_id": order["id"],
            "amount": amount,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan": plan,
            "plan_name": info["name"],
            "email": request.user.email,
        })


class VerifyPaymentView(APIView):
    def post(self, request):
        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")

        payment = Payment.objects.filter(
            user=request.user, razorpay_order_id=order_id, status="created"
        ).first()
        if not payment or not payment_id:
            return Response({"error": "Unknown or already processed order."}, status=400)
        if not verify_razorpay_signature(order_id, payment_id, signature):
            payment.status = "failed"
            payment.save(update_fields=["status"])
            return Response({"error": "Payment verification failed."}, status=400)

        payment.status = "paid"
        payment.razorpay_payment_id = payment_id
        payment.paid_at = timezone.now()
        payment.save()
        activate_plan(request.user, payment.plan)
        return Response({"message": "Subscription activated.", "quota": quota_summary(request.user)})
