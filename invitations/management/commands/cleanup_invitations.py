from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.utils import purge_old_otps
from invitations.media import delete_invitation_files
from invitations.models import Invitation


class Command(BaseCommand):
    help = "Delete never-deployed invitations (and their media) untouched for N days, plus old OTPs."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, days, dry_run, **options):
        cutoff = timezone.now() - timedelta(days=days)
        stale = Invitation.objects.filter(is_deployed=False, updated_at__lt=cutoff)
        count = stale.count()
        if not dry_run:
            for invitation in stale:
                delete_invitation_files(invitation)
                invitation.delete()
            purge_old_otps()
        verb = "Would delete" if dry_run else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} stale invitations."))
