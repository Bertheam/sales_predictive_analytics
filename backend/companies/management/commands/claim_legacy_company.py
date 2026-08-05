from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from companies.models import Company, Membership


LEGACY_COMPANY_ID = "00000000-0000-4000-8000-000000000001"


class Command(BaseCommand):
    help = "Rattache les données historiques au compte propriétaire indiqué."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Adresse e-mail du compte Django existant")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'ajout même si un autre propriétaire existe déjà.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"Aucun compte Django ne correspond à {email}.") from exc
        try:
            company = Company.objects.get(pk=LEGACY_COMPANY_ID)
        except Company.DoesNotExist as exc:
            raise CommandError(
                "Le dépôt historique n'existe pas encore. Appliquez d'abord les migrations."
            ) from exc

        other_owner_exists = company.memberships.filter(
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        ).exclude(user=user).exists()
        if other_owner_exists and not options["force"]:
            raise CommandError(
                "Ce dépôt possède déjà un autre propriétaire actif. "
                "Utilisez --force uniquement après vérification."
            )

        membership, created = Membership.objects.update_or_create(
            company=company,
            user=user,
            defaults={
                "role": Membership.Role.OWNER,
                "status": Membership.Status.ACTIVE,
                "joined_at": timezone.now(),
            },
        )
        action = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            f"Accès propriétaire {action} : {user.email} → {company.name}."
        ))
