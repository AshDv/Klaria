"""Invitations de consentement accessibles, sobres et sans suivi publicitaire."""

import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from textwrap import dedent
from zoneinfo import ZoneInfo

from app.config import settings


class EmailError(RuntimeError):
    pass


def sender() -> str:
    return formataddr(("Klaria", settings.smtp_from_email or ""))


def _date(value: datetime | None) -> str:
    if not value:
        return "Horaire communiqué séparément"
    source = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
    return source.astimezone(ZoneInfo("Europe/Paris")).strftime(
        "%d/%m/%Y à %H:%M (heure de Paris)"
    )


def send_consent_email(
    name: str,
    email: str,
    title: str,
    token: str,
    media_retention_days: int = 0,
    scheduled_at: datetime | None = None,
    organizer_name: str | None = None,
    organizer_email: str | None = None,
    platform: str | None = None,
) -> None:
    if not settings.smtp_configured:
        raise EmailError("Le serveur d’e-mail SMTP n’est pas configuré")

    link = f"{settings.frontend_url.rstrip('/')}/consent/{token}"
    platform_label = {
        "google_meet": "Google Meet",
        "teams": "Microsoft Teams",
        "in_person": "Réunion en présentiel",
    }.get(platform or "", "Réunion")
    media_notice = (
        f"Un replay audio sera conservé pendant {media_retention_days} jour(s) maximum."
        if media_retention_days
        else "L’audio du bot n’est pas conservé par Klaria."
    )
    organizer = organizer_name or organizer_email or "L’organisateur"
    plain = f"""Bonjour {name},

{organizer} souhaite utiliser Klaria pendant « {title} ».
Date : {_date(scheduled_at)}
Plateforme : {platform_label}

Klaria transcrit les échanges, distingue les voix et utilise Mistral AI pour produire
un compte rendu, les décisions et les actions. {media_notice} Klaria ne capture ni la
vidéo ni le partage d’écran.
Le chat est uniquement lu pour détecter STOP KLARIA et n’est pas conservé.

Consultez les informations puis acceptez ou refusez ici : {link}

La capture ne commence pas sans l’accord de chaque participant. Vous pourrez retirer
votre accord depuis le même lien ou écrire STOP KLARIA pendant la réunion.
Contact données personnelles : {settings.privacy_contact_email}
"""

    safe = {
        "name": escape(name),
        "title": escape(title),
        "date": escape(_date(scheduled_at)),
        "platform": escape(platform_label),
        "organizer": escape(organizer),
        "media": escape(media_notice),
        "link": escape(link, quote=True),
        "privacy": escape(settings.privacy_contact_email),
    }
    html = dedent(
        f"""\
        <!doctype html>
        <html lang="fr">
        <body style="margin:0;background:#f4f6f5;color:#17211d;font-family:Arial,sans-serif">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
        <tr><td align="center" style="padding:32px 12px">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:620px;background:#fff;border:1px solid #dfe5e2;
                 border-radius:20px;overflow:hidden">
        <tr><td style="padding:24px 30px;background:#123f34;color:#fff">
          <b style="font-size:20px">Klaria</b>
          <span style="float:right;font-size:12px;color:#bfe0d4">Consentement préalable</span>
        </td></tr>
        <tr><td style="padding:34px 30px 12px">
          <div style="font-size:12px;font-weight:700;color:#176852;text-transform:uppercase;
                      letter-spacing:1px">Invitation sécurisée</div>
          <h1 style="margin:12px 0 10px;font-size:26px;line-height:1.25">
            Bonjour {safe['name']}, votre choix est requis
          </h1>
          <p style="margin:0;color:#52605b;line-height:1.6">
            {safe['organizer']} souhaite utiliser Klaria pendant la réunion
            <b>« {safe['title']} »</b>.
          </p>
        </td></tr>
        <tr><td style="padding:12px 30px">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
            style="background:#f4f8f6;border-radius:14px">
          <tr>
            <td style="padding:18px"><div style="font-size:12px;color:#68746f">DATE</div>
              <b>{safe['date']}</b></td>
            <td style="padding:18px"><div style="font-size:12px;color:#68746f">PLATEFORME</div>
              <b>{safe['platform']}</b></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:16px 30px;color:#3d4945;line-height:1.65">
          <b>Ce que fait Klaria</b>
          <p style="margin:8px 0">Il transcrit les échanges, distingue les intervenants et
            utilise Mistral AI pour produire le compte rendu, les décisions et les actions.</p>
          <p style="margin:8px 0">{safe['media']} Klaria ne capture ni la vidéo ni le
            partage d’écran.</p>
          <p style="margin:8px 0">Le chat sert uniquement à détecter <b>STOP KLARIA</b>
            et n’est pas conservé.</p>
        </td></tr>
        <tr><td align="center" style="padding:12px 30px 26px">
          <a href="{safe['link']}"
            style="display:inline-block;padding:14px 24px;border-radius:11px;background:#176852;
                   color:#fff;text-decoration:none;font-weight:700">
            Consulter et faire mon choix
          </a>
          <p style="margin:14px 0 0;font-size:12px;color:#68746f">
            La capture ne commence pas sans l’accord de chaque participant.
          </p>
        </td></tr>
        <tr><td style="padding:20px 30px;background:#f7f9f8;border-top:1px solid #e5eae7;
                      color:#68746f;font-size:12px;line-height:1.55">
          Vous pouvez retirer votre accord depuis le même lien ou écrire STOP KLARIA pendant
          la réunion.<br>
          Contact données personnelles :
          <a href="mailto:{safe['privacy']}" style="color:#176852">{safe['privacy']}</a><br><br>
          Cet e-mail ne contient aucun traceur publicitaire.
        </td></tr>
        </table></td></tr></table>
        </body></html>
        """
    )

    message = EmailMessage()
    message["Subject"] = f"Votre accord est requis avant « {title} »"
    message["From"] = sender()
    message["To"] = email
    message["Reply-To"] = organizer_email or settings.privacy_contact_email
    message.set_content(plain)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailError("L’invitation n’a pas pu être envoyée") from exc


def send_report_email(name: str, email: str, title: str, summary: str, link: str) -> None:
    """Envoie un compte rendu sans traceur à un participant autorisé."""
    if not settings.smtp_configured:
        raise EmailError("Le serveur d’e-mail SMTP n’est pas configuré")
    safe_name, safe_title = escape(name), escape(title)
    safe_summary, safe_link = escape(summary), escape(link, quote=True)
    message = EmailMessage()
    message["Subject"] = f"Compte rendu — {title}"
    message["From"] = sender()
    message["To"] = email
    message["Reply-To"] = settings.privacy_contact_email
    message.set_content(
        f"Bonjour {name},\n\nLe compte rendu de « {title} » est prêt.\n\n"
        f"{summary}\n\nConsulter : {link}\n"
    )
    message.add_alternative(
        dedent(
            f"""<!doctype html><html lang="fr"><body style="margin:0;background:#f4f6f5;
            color:#17211d;font-family:Arial,sans-serif"><table role="presentation" width="100%">
            <tr><td align="center" style="padding:32px 12px"><table role="presentation"
            width="100%" style="max-width:620px;background:#fff;border:1px solid #dfe5e2;
            border-radius:20px"><tr><td style="padding:24px 30px;background:#123f34;color:#fff;
            border-radius:20px 20px 0 0"><b style="font-size:20px">Klaria</b></td></tr>
            <tr><td style="padding:32px 30px"><p>Bonjour {safe_name},</p><h1 style="font-size:25px">
            {safe_title}</h1><p style="line-height:1.65;color:#52605b">{safe_summary}</p>
            <a href="{safe_link}" style="display:inline-block;margin-top:12px;padding:14px 22px;
            background:#176852;color:#fff;text-decoration:none;border-radius:11px;font-weight:700">
            Ouvrir le compte rendu</a></td></tr><tr><td style="padding:18px 30px;background:#f7f9f8;
            color:#68746f;font-size:12px;border-radius:0 0 20px 20px">Aucun traceur publicitaire.
            Les accès restent contrôlés par Klaria.</td></tr></table></td></tr></table>
            </body></html>"""
        ),
        subtype="html",
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailError("Le compte rendu n’a pas pu être envoyé") from exc
