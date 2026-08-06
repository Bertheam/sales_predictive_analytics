import logging
import smtplib

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from .emails import send_company_invitation_email
from .models import CompanyInvitation
from .services import hash_invitation_token


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="companies.tasks.send_company_invitation",
    max_retries=3,
)
def send_company_invitation(self, invitation_id, raw_token, accept_url):
    """Send only the latest valid link and persist the SMTP hand-off status."""
    invitation = CompanyInvitation.objects.select_related(
        "company", "invited_by"
    ).filter(pk=invitation_id).first()
    if invitation is None:
        return {"status": "missing"}
    if (
        invitation.status != CompanyInvitation.Status.PENDING
        or invitation.token_hash != hash_invitation_token(raw_token)
    ):
        return {"status": "stale"}

    now = timezone.now()
    CompanyInvitation.objects.filter(pk=invitation.pk).update(
        email_status=CompanyInvitation.EmailStatus.SENDING,
        email_attempts=F("email_attempts") + 1,
        email_error="",
        last_email_task_id=self.request.id or invitation.last_email_task_id,
        updated_at=now,
    )
    invitation.refresh_from_db()
    try:
        sent = send_company_invitation_email(
            invitation=invitation,
            accept_url=accept_url,
        )
        if not sent:
            raise smtplib.SMTPException("Le serveur SMTP n’a accepté aucun message.")
    except (OSError, smtplib.SMTPException) as exc:
        error = str(exc)[:2000]
        if self.request.retries < self.max_retries:
            CompanyInvitation.objects.filter(pk=invitation.pk).update(
                email_status=CompanyInvitation.EmailStatus.QUEUED,
                email_error=error,
                updated_at=timezone.now(),
            )
            raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
        CompanyInvitation.objects.filter(pk=invitation.pk).update(
            email_status=CompanyInvitation.EmailStatus.FAILED,
            email_failed_at=timezone.now(),
            email_error=error,
            updated_at=timezone.now(),
        )
        logger.exception("Échec définitif de l’invitation %s", invitation.pk)
        raise

    CompanyInvitation.objects.filter(pk=invitation.pk).update(
        email_status=CompanyInvitation.EmailStatus.SENT,
        email_sent_at=timezone.now(),
        email_failed_at=None,
        email_error="",
        updated_at=timezone.now(),
    )
    return {"status": "sent", "invitation_id": str(invitation.pk)}


def queue_company_invitation_email(*, invitation, raw_token, accept_url):
    """Queue an invitation without turning a broker outage into an HTTP 500."""
    now = timezone.now()
    CompanyInvitation.objects.filter(pk=invitation.pk).update(
        email_status=CompanyInvitation.EmailStatus.QUEUED,
        email_queued_at=now,
        email_failed_at=None,
        email_error="",
        updated_at=now,
    )
    try:
        result = send_company_invitation.delay(
            str(invitation.pk), raw_token, accept_url
        )
    except Exception as exc:
        logger.exception("Impossible de mettre l’invitation %s en file", invitation.pk)
        CompanyInvitation.objects.filter(pk=invitation.pk).update(
            email_status=CompanyInvitation.EmailStatus.FAILED,
            email_failed_at=timezone.now(),
            email_error=str(exc)[:2000],
            updated_at=timezone.now(),
        )
        return False
    CompanyInvitation.objects.filter(pk=invitation.pk).update(
        last_email_task_id=result.id or "",
        updated_at=timezone.now(),
    )
    return True
