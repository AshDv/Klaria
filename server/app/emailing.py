"""Envoi minimal des invitations de consentement par SMTP."""

import smtplib
from email.message import EmailMessage

from app.config import settings


class EmailError(RuntimeError):
    pass


def send_consent_email(name: str, email: str, title: str, token: str) -> None:
    if not settings.smtp_configured:
        raise EmailError("Le serveur d’e-mail SMTP n’est pas configuré")

    link = f"{settings.frontend_url.rstrip('/')}/consent/{token}"
    message = EmailMessage()
    message["Subject"] = f"Votre accord est requis avant « {title} »"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(
        f"""Bonjour {name},

Vous êtes invité à une réunion intitulée « {title} ».
Scribe enregistrera la voix des participants, transmettra l’audio à Mistral AI
pour transcription et utilisera Mistral Medium 3.5 pour produire un compte rendu.

Vous pouvez accepter ou refuser librement, puis retirer votre accord à tout moment :
{link}

Sans l’accord de chaque participant, l’enregistrement ne pourra pas commencer.
Contact données personnelles : {settings.privacy_contact_email}
"""
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailError("L’invitation n’a pas pu être envoyée") from exc
