from django.core.management.base import BaseCommand

from invitations.library import sync_templates


class Command(BaseCommand):
    help = "Load templates_library/*/config.json into the database."

    def handle(self, *args, **options):
        synced = sync_templates()
        self.stdout.write(self.style.SUCCESS(f"Synced {len(synced)} templates: {', '.join(synced)}"))
