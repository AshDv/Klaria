"""Synchronisation minimale des agendas Google et Microsoft."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.consent_routes import ParticipantInput, SessionInput, create_consent_session
from app.db import engine
from app.models import (
    CalendarConnection,
    CalendarEvent,
    CalendarEventStatus,
    CalendarProvider,
    ConsentSession,
    ConsentSessionStatus,
    ParticipantConsent,
    User,
    utc_now,
)
from app.token_crypto import decrypt_token, encrypt_token

MEETING_URL = re.compile(
    r"https://(?:meet\.google\.com/[a-z-]+|teams\.(?:live|microsoft)\.com/[^\s<>\"]+)",
    re.IGNORECASE,
)


class CalendarError(RuntimeError):
    pass


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def meeting_url(*values: str | None) -> str | None:
    for value in values:
        if match := MEETING_URL.search(value or ""):
            return match.group(0).rstrip(".,)")
    return None


def _request(method: str, url: str, **kwargs) -> dict:
    try:
        response = httpx.request(method, url, timeout=20, **kwargs)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CalendarError("Le fournisseur d’agenda n’a pas répondu correctement") from exc


def create_follow_up(
    connection: CalendarConnection,
    db: Session,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    attendees: list[dict],
) -> dict:
    """Crée une réunion en ligne et laisse le fournisseur envoyer les invitations."""
    token = access_token(connection, db)
    if connection.provider == CalendarProvider.GOOGLE:
        return _request(
            "POST",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json={
                "summary": title,
                "start": {"dateTime": aware(starts_at).isoformat(), "timeZone": "Europe/Paris"},
                "end": {"dateTime": aware(ends_at).isoformat(), "timeZone": "Europe/Paris"},
                "attendees": [{"email": item["email"]} for item in attendees],
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"scribe-{int(utc_now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            },
        )
    return _request(
        "POST",
        "https://graph.microsoft.com/v1.0/me/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subject": title,
            "start": {"dateTime": aware(starts_at).isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": aware(ends_at).isoformat(), "timeZone": "UTC"},
            "attendees": [
                {
                    "emailAddress": {"address": item["email"], "name": item.get("name")},
                    "type": "required",
                }
                for item in attendees
            ],
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        },
    )


def _refresh(connection: CalendarConnection, db: Session) -> str:
    refresh_token = decrypt_token(connection.refresh_token)
    if not refresh_token:
        raise CalendarError("Reconnectez cet agenda pour renouveler son autorisation")
    if connection.provider == CalendarProvider.GOOGLE:
        data = _request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    else:
        data = _request(
            "POST",
            f"https://login.microsoftonline.com/{settings.microsoft_tenant}/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": settings.microsoft_calendar_scopes,
            },
        )
    access = data.get("access_token")
    if not access:
        raise CalendarError("Le fournisseur n’a pas renouvelé l’accès à l’agenda")
    connection.access_token = encrypt_token(access) or ""
    if data.get("refresh_token"):
        connection.refresh_token = encrypt_token(data["refresh_token"])
    connection.token_expires_at = utc_now() + timedelta(seconds=int(data.get("expires_in", 3600)))
    connection.updated_at = utc_now()
    db.add(connection)
    db.commit()
    return access


def access_token(connection: CalendarConnection, db: Session) -> str:
    expires = aware(connection.token_expires_at)
    if not expires or expires <= utc_now() + timedelta(minutes=2):
        return _refresh(connection, db)
    token = decrypt_token(connection.access_token)
    if not token:
        raise CalendarError("L’autorisation de l’agenda est vide")
    return token


def _google_events(connection: CalendarConnection, db: Session) -> list[dict]:
    token = access_token(connection, db)
    now = utc_now()
    params = {
        "timeMin": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "timeMax": (now + timedelta(days=60)).isoformat().replace("+00:00", "Z"),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    }
    data = _request(
        "GET",
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    return data.get("items", [])


def _microsoft_events(connection: CalendarConnection, db: Session) -> list[dict]:
    token = access_token(connection, db)
    now = utc_now()
    params = {
        "startDateTime": (now - timedelta(days=1)).isoformat(),
        "endDateTime": (now + timedelta(days=60)).isoformat(),
        "$top": 250,
        "$select": (
            "id,subject,start,end,attendees,organizer,onlineMeeting,"
            "onlineMeetingUrl,isCancelled,bodyPreview,location"
        ),
        "$orderby": "start/dateTime",
    }
    data = _request(
        "GET",
        "https://graph.microsoft.com/v1.0/me/calendarView",
        headers={
            "Authorization": f"Bearer {token}",
            "Prefer": 'outlook.timezone="UTC"',
        },
        params=params,
    )
    return data.get("value", [])


def _google_item(item: dict, owner_email: str) -> dict | None:
    url = meeting_url(
        item.get("hangoutLink"),
        json.dumps(item.get("conferenceData") or {}),
        item.get("location"),
        item.get("description"),
    )
    starts = parse_datetime((item.get("start") or {}).get("dateTime"))
    if not url or not starts:
        return None
    attendees = [
        {
            "name": person.get("displayName") or person.get("email", "").split("@")[0],
            "email": person.get("email", "").lower(),
        }
        for person in item.get("attendees", [])
        if person.get("email")
        and not person.get("resource")
        and person.get("responseStatus") != "declined"
        and person.get("email", "").lower() != owner_email.lower()
    ]
    return {
        "provider_event_id": item["id"],
        "title": item.get("summary") or "Réunion sans titre",
        "starts_at": starts,
        "ends_at": parse_datetime((item.get("end") or {}).get("dateTime")),
        "meeting_url": url,
        "organizer_email": (item.get("organizer") or {}).get("email"),
        "attendees": attendees,
        "cancelled": item.get("status") == "cancelled",
    }


def _microsoft_item(item: dict, owner_email: str) -> dict | None:
    online = item.get("onlineMeeting") or {}
    url = meeting_url(
        online.get("joinUrl"),
        item.get("onlineMeetingUrl"),
        (item.get("location") or {}).get("displayName"),
        item.get("bodyPreview"),
    )
    starts = parse_datetime((item.get("start") or {}).get("dateTime"))
    if not url or not starts:
        return None
    attendees = []
    for person in item.get("attendees", []):
        address = (person.get("emailAddress") or {}).get("address", "").lower()
        if not address or person.get("type") == "resource" or address == owner_email.lower():
            continue
        attendees.append(
            {
                "name": (person.get("emailAddress") or {}).get("name") or address.split("@")[0],
                "email": address,
            }
        )
    organizer = (item.get("organizer") or {}).get("emailAddress") or {}
    return {
        "provider_event_id": item["id"],
        "title": item.get("subject") or "Réunion sans titre",
        "starts_at": starts,
        "ends_at": parse_datetime((item.get("end") or {}).get("dateTime")),
        "meeting_url": url,
        "organizer_email": organizer.get("address"),
        "attendees": attendees,
        "cancelled": bool(item.get("isCancelled")),
    }


def _ensure_consent(
    event: CalendarEvent,
    db: Session,
    media_recording_enabled: bool = False,
    media_retention_days: int = 7,
) -> None:
    if event.consent_session_id or not event.auto_join:
        return
    attendees = json.loads(event.attendees_json)
    if not attendees:
        return
    payload = SessionInput(
        title=event.title,
        scheduled_at=event.starts_at,
        participants=[ParticipantInput(**person) for person in attendees],
        media_recording_enabled=media_recording_enabled,
        media_retention_days=media_retention_days,
        platform=(
            "google_meet" if "meet.google.com" in event.meeting_url else "teams"
        ),
    )
    meeting, failed = create_consent_session(event.owner_id, payload, db)
    event.consent_session_id = meeting.id
    event.invitation_errors_json = json.dumps(failed)
    db.add(event)
    db.commit()


def sync_connection(connection: CalendarConnection, db: Session) -> int:
    raw = (
        _google_events(connection, db)
        if connection.provider == CalendarProvider.GOOGLE
        else _microsoft_events(connection, db)
    )
    parser = _google_item if connection.provider == CalendarProvider.GOOGLE else _microsoft_item
    count = 0
    for raw_item in raw:
        item = parser(raw_item, connection.account_email)
        if not item:
            continue
        event = db.exec(
            select(CalendarEvent).where(
                CalendarEvent.connection_id == connection.id,
                CalendarEvent.provider_event_id == item["provider_event_id"],
            )
        ).first()
        ends_at = aware(item["ends_at"] or item["starts_at"])
        if not event and ends_at and ends_at < utc_now():
            continue
        if not event:
            event = CalendarEvent(
                owner_id=connection.user_id,
                connection_id=connection.id,
                provider_event_id=item["provider_event_id"],
                title=item["title"],
                starts_at=item["starts_at"],
                ends_at=item["ends_at"],
                meeting_url=item["meeting_url"],
                organizer_email=item["organizer_email"],
                attendees_json=json.dumps(item["attendees"], ensure_ascii=False),
                auto_join=connection.auto_join_tagged and "[scribe]" in item["title"].lower(),
            )
        else:
            previous_attendees = event.attendees_json
            event.title = item["title"]
            event.starts_at = item["starts_at"]
            event.ends_at = item["ends_at"]
            event.meeting_url = item["meeting_url"]
            event.organizer_email = item["organizer_email"]
            event.attendees_json = json.dumps(item["attendees"], ensure_ascii=False)
            if previous_attendees != event.attendees_json and event.consent_session_id:
                previous_consent = db.get(ConsentSession, event.consent_session_id)
                if previous_consent and not event.remote_meeting_id:
                    previous_consent.status = ConsentSessionStatus.STOPPED
                    previous_consent.stopped_at = utc_now()
                    db.add(previous_consent)
                    event.consent_session_id = None
                event.auto_join = False
                event.invitation_errors_json = json.dumps(
                    ["Invités modifiés : vérifiez et réactivez Scribe"]
                )
        event.status = (
            CalendarEventStatus.CANCELLED if item["cancelled"] else CalendarEventStatus.SCHEDULED
        )
        event.last_synced_at = utc_now()
        db.add(event)
        db.commit()
        _ensure_consent(event, db)
        count += 1
    connection.last_synced_at = utc_now()
    connection.updated_at = utc_now()
    db.add(connection)
    db.commit()
    return count


def calendar_event_detail(event: CalendarEvent) -> dict:
    return {
        "id": event.id,
        "provider_event_id": event.provider_event_id,
        "title": event.title,
        "starts_at": aware(event.starts_at).isoformat(),
        "ends_at": aware(event.ends_at).isoformat() if event.ends_at else None,
        "meeting_url": event.meeting_url,
        "platform": "google_meet" if "meet.google.com" in event.meeting_url else "teams",
        "organizer_email": event.organizer_email,
        "attendees": json.loads(event.attendees_json),
        "status": event.status,
        "auto_join": event.auto_join,
        "consent_session_id": event.consent_session_id,
        "remote_meeting_id": event.remote_meeting_id,
        "invitation_errors": json.loads(event.invitation_errors_json),
        "bot_started_at": aware(event.bot_started_at).isoformat() if event.bot_started_at else None,
    }


def run_automation(db: Session) -> dict:
    now = utc_now()
    synced = 0
    errors: list[str] = []
    for connection in db.exec(select(CalendarConnection).where(CalendarConnection.active)):
        last_sync = aware(connection.last_synced_at)
        if not last_sync or last_sync <= now - timedelta(minutes=settings.calendar_sync_minutes):
            try:
                synced += sync_connection(connection, db)
            except CalendarError as exc:
                errors.append(f"{connection.provider}: {exc}")

    started = 0
    events = db.exec(
        select(CalendarEvent).where(
            CalendarEvent.auto_join,
            CalendarEvent.status == CalendarEventStatus.SCHEDULED,
            CalendarEvent.remote_meeting_id.is_(None),
        )
    )
    for event in events:
        starts = aware(event.starts_at)
        if not starts or not (
            starts - timedelta(seconds=settings.bot_join_seconds_before)
            <= now
            <= starts + timedelta(minutes=settings.bot_join_grace_minutes)
        ):
            continue
        consent = (
            db.get(ConsentSession, event.consent_session_id) if event.consent_session_id else None
        )
        participants = list(
            db.exec(
                select(ParticipantConsent).where(
                    ParticipantConsent.session_id == event.consent_session_id
                )
            )
        )
        if (
            not consent
            or not participants
            or not all(item.consented_at and not item.withdrawn_at for item in participants)
        ):
            continue
        consent.status = ConsentSessionStatus.RECORDING
        consent.notice_confirmed_at = now
        consent.started_at = now
        db.add(consent)
        db.commit()
        user = db.get(User, event.owner_id)
        if not user:
            continue
        try:
            from app.remote_routes import launch_remote_meeting

            remote = launch_remote_meeting(consent, user, event.meeting_url, "fr", db)
            event.remote_meeting_id = remote.id
            event.bot_started_at = now
            db.add(event)
            db.commit()
            started += 1
        except Exception as exc:  # Le prochain passage peut retenter sans dupliquer le bot.
            consent.status = ConsentSessionStatus.READY
            consent.started_at = None
            consent.notice_confirmed_at = None
            db.add(consent)
            db.commit()
            errors.append(f"{event.id}: {exc}")
    return {"synced": synced, "started": started, "errors": errors}


async def automation_loop() -> None:
    """Garde les agendas synchronisés et prépare le bot avant l'heure prévue."""
    while True:
        try:
            await asyncio.to_thread(_automation_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(max(10, settings.automation_interval_seconds))


def _automation_once() -> None:
    with Session(engine) as db:
        run_automation(db)
