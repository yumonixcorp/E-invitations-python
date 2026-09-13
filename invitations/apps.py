from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_library(sender, **kwargs):
    from .library import sync_templates

    sync_templates()


class InvitationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invitations"

    def ready(self):
        # Load/refresh the 10 templates from templates_library/ after every migrate.
        post_migrate.connect(_sync_library, sender=self)
