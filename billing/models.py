from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.CharField(max_length=50, default="free")
    invitations_used_this_month = models.IntegerField(default=0)
    last_reset_date = models.DateField(default=timezone.localdate)
    expires_at = models.DateTimeField(null=True, blank=True)  # paid plans only
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user} - {self.plan}"


class Payment(models.Model):
    STATUS_CHOICES = [("created", "Created"), ("paid", "Paid"), ("failed", "Failed")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.CharField(max_length=50)
    amount_paise = models.PositiveIntegerField()
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.razorpay_order_id} ({self.status})"
