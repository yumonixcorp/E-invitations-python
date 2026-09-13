from django.contrib import admin

from .models import Invitation, Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "template", "is_deployed", "live_url", "created_at")
    list_filter = ("is_deployed", "template")
    search_fields = ("user__email", "live_url")
    readonly_fields = ("netlify_site_id", "last_deployed_at", "created_at", "updated_at")
