from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import OTP, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "is_email_verified", "is_staff", "date_joined")
    fieldsets = UserAdmin.fieldsets + (("Verification", {"fields": ("is_email_verified",)}),)


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "created_at", "is_used", "attempts")
    list_filter = ("purpose", "is_used")
    readonly_fields = ("code",)
