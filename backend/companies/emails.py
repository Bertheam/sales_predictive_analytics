from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


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
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invitation.email],
    )
    message.attach_alternative(html_body, "text/html")
    return message.send(fail_silently=False)
