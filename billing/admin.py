from django.contrib import admin

from .models import Payment, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "invitations_used_this_month", "last_reset_date", "expires_at", "is_active")
    list_filter = ("plan", "is_active")
    search_fields = ("user__email",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("razorpay_order_id", "user", "plan", "amount_paise", "status", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("user__email", "razorpay_order_id", "razorpay_payment_id")
