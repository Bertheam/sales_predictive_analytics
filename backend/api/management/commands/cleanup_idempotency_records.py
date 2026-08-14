from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import IdempotencyRecord


class Command(BaseCommand):
    help = "Supprime les réponses d'idempotence API arrivées à expiration."

    def handle(self, *args, **options):
        deleted, _ = IdempotencyRecord.objects.filter(
            expires_at__lte=timezone.now()
        ).delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} enregistrement(s) supprimé(s)."))
