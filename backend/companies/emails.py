import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class BrevoAPIError(OSError):
    """Safe, retryable error raised by the Brevo HTTPS transport."""


def _send_with_brevo_api(*, recipient, subject, text_body, html_body):
    sender_name, sender_email = parseaddr(settings.DEFAULT_FROM_EMAIL)
    if not sender_email:
        raise BrevoAPIError("L’adresse expéditrice DEFAULT_FROM_EMAIL est invalide.")
    payload = {
        "sender": {"email": sender_email, "name": sender_name or "NexaStock"},
        "to": [{"email": recipient}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
        "tags": ["nexastock-invitation"],
    }
    request = Request(
        settings.BREVO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("message", "")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = ""
        raise BrevoAPIError(
            f"Brevo API HTTP {exc.code}{f': {detail}' if detail else ''}"
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BrevoAPIError(f"Brevo API indisponible : {exc}") from exc
    message_id = body.get("messageId", "")
    if not message_id:
        raise BrevoAPIError("Brevo n’a retourné aucun identifiant de message.")
    return message_id


def send_company_invitation_email(*, invitation, accept_url):
    """Send the responsive HTML invitation with a plain-text fallback."""

    invited_by_name = "L’équipe du dépôt"
    if invitation.invited_by:
        invited_by_name = (
            invitation.invited_by.full_name or invitation.invited_by.email
        )
    context = {
        "accept_url": accept_url,
        "company": invitation.company,
        "expires_at": invitation.expires_at,
        "invitation": invitation,
        "invited_by_name": invited_by_name,
        "role_label": invitation.get_role_display(),
    }
    subject = f"Invitation à rejoindre {invitation.company.name} sur NexaStock"
    text_body = render_to_string("emails/company_invitation.txt", context)
    html_body = render_to_string("emails/company_invitation.html", context)
    if settings.BREVO_API_KEY:
        return _send_with_brevo_api(
            recipient=invitation.email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invitation.email],
    )
    message.attach_alternative(html_body, "text/html")
    return message.send(fail_silently=False)
