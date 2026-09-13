"""Monthly invitation quota: free plan = 1 invitation per email per month."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Subscription


def plan_info(plan):
    return settings.PLANS.get(plan, settings.PLANS["free"])


def _refresh(sub):
    """Expire lapsed paid plans and reset the counter when a new month starts."""
    today = timezone.localdate()
    changed = False
    if sub.plan != "free" and sub.expires_at and sub.expires_at <= timezone.now():
        sub.plan = "free"
        sub.expires_at = None
        changed = True
    if (sub.last_reset_date.year, sub.last_reset_date.month) != (today.year, today.month):
        sub.invitations_used_this_month = 0
        sub.last_reset_date = today
        changed = True
    if changed:
        sub.save()
    return sub


def get_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user)
    return _refresh(sub)


def _has_room(sub):
    limit = plan_info(sub.plan)["monthly_limit"]
    return limit is None or sub.invitations_used_this_month < limit


def can_create_invitation(user):
    return _has_room(get_subscription(user))


def reserve_invitation_slot(user):
    """Atomically check the quota and count one invitation. Returns True if allowed."""
    with transaction.atomic():
        Subscription.objects.get_or_create(user=user)
        sub = _refresh(Subscription.objects.select_for_update().get(user=user))
        if not sub.is_active or not _has_room(sub):
            return False
        sub.invitations_used_this_month += 1
        sub.save(update_fields=["invitations_used_this_month"])
        return True


def activate_plan(user, plan):
    with transaction.atomic():
        Subscription.objects.get_or_create(user=user)
        sub = _refresh(Subscription.objects.select_for_update().get(user=user))
        start = timezone.now()
        if sub.plan == plan and sub.expires_at and sub.expires_at > start:
            start = sub.expires_at  # renewing extends the current period
        sub.plan = plan
        sub.expires_at = start + timedelta(days=settings.PAID_PLAN_DAYS)
        sub.is_active = True
        sub.save()
        return sub


def quota_summary(user):
    sub = get_subscription(user)
    info = plan_info(sub.plan)
    limit = info["monthly_limit"]
    return {
        "plan": sub.plan,
        "plan_name": info["name"],
        "used": sub.invitations_used_this_month,
        "limit": limit,
        "remaining": None if limit is None else max(limit - sub.invitations_used_this_month, 0),
        "expires_at": sub.expires_at,
    }
