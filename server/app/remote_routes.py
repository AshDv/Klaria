"""API du bot de réunion Google Meet et Microsoft Teams."""

import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Literal

import websockets
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, WebSocket
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from starlette.responses import StreamingResponse

from app import vexa
from app.auth import current_user, user_id_from_token
from app.config import settings
from app.consent_routes import is_active, participants_for
from app.db import engine, get_session
from app.emailing import EmailError, send_report_email
from app.llm import SummaryError, generate_podcast
from app.meeting_artifacts import google_meet_context
from app.meeting_skills import public_skills
from app.models import (
    CalendarConnection,
    CalendarEvent,
    ConsentSession,
    ConsentSessionStatus,
    ParticipantConsent,
    Recording,
    RemoteMeeting,
    RemoteMeetingStatus,
    User,
    utc_now,
)
from app.remote_monitor import watch_remote_meeting
from app.remote_processing import (
    chat_sender,
    finalize_remote_meeting,
    is_stop_command,
    reanalyze_remote_meeting,
    stop_and_erase_remote_meeting,
    stop_for_participant,
    sync_remote_meeting,
)

router = APIRouter(prefix="/api")


class RemoteMeetingInput(BaseModel):
    consent_session_id: str
    meeting_url: str = Field(min_length=15, max_length=2000)
    language: str = Field(default="fr", pattern=r"^[a-z]{2}$")


class PodcastInput(BaseModel):
    format: Literal["deep_dive", "brief", "critique", "debate"] = "deep_dive"
    minutes: int = Field(default=5, ge=1, le=15)
    focus: str | None = Field(default=None, max_length=300)


class ActionUpdate(BaseModel):
    owner_email: str | None = Field(default=None, max_length=320)
    due_date: str | None = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    priority: Literal["low", "medium", "high"] | None = None


class ReportEmailInput(BaseModel):
    recipient_emails: list[str] = Field(min_length=1, max_length=50)


class FollowUpInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=480)
    participant_emails: list[str] = Field(min_length=1, max_length=50)
    calendar_connection_id: str | None = None


@router.websocket("/remote-meetings/{meeting_id}/live")
async def remote_meeting_live(websocket: WebSocket, meeting_id: str):
    """Relaie le WebSocket Vexa sans exposer sa clé au navigateur."""
    protocols = [
        item.strip() for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
    ]
    user_id = user_id_from_token(protocols[1]) if len(protocols) == 2 else None
    with Session(engine) as db:
        meeting = db.get(RemoteMeeting, meeting_id)
        allowed = bool(meeting and user_id and meeting.owner_id == user_id)
        platform = meeting.platform if allowed else None
        native_id = meeting.native_id if allowed else None
    if not allowed:
        await websocket.close(code=4401)
        return
    await websocket.accept(subprotocol="nolya")
    try:
        async with websockets.connect(
            vexa.websocket_url(),
            additional_headers={"X-API-Key": vexa.api_key()},
            ping_interval=25,
        ) as provider:
            await provider.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "meetings": [{"platform": platform, "native_id": native_id}],
                    }
                )
            )
            async for raw in provider:
                event = json.loads(raw)
                if event.get("type") == "transcript.mutable":
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "segments": vexa.normalize_segments(event.get("payload") or {}),
                        }
                    )
                elif event.get("type") == "meeting.status":
                    await websocket.send_json(
                        {"type": "status", "status": (event.get("payload") or {}).get("status")}
                    )
                elif event.get("type") == "chat.received":
                    payload = event.get("payload") or {}
                    if is_stop_command(str(payload.get("text") or "")):
                        stop_for_participant(meeting_id, chat_sender(payload))
                        await websocket.send_json(
                            {"type": "status", "status": "stopped", "reason": "chat"}
                        )
                        break
    except (OSError, ValueError, websockets.WebSocketException):
        with suppress(RuntimeError):
            await websocket.close(code=1011)


def owned_remote(meeting_id: str, user: User, db: Session) -> RemoteMeeting:
    meeting = db.get(RemoteMeeting, meeting_id)
    if not meeting or meeting.owner_id != user.id:
        raise HTTPException(404, "Réunion distante introuvable")
    return meeting


def remote_detail(meeting: RemoteMeeting) -> dict:
    report = json.loads(meeting.report_json) if meeting.report_json else None
    segments = vexa.normalize_timeline(json.loads(meeting.segments_json or "[]"))
    duration = int(max((item["end"] for item in segments), default=meeting.duration_seconds))
    with Session(engine) as db:
        participants = list(
            db.exec(
                select(ParticipantConsent).where(
                    ParticipantConsent.session_id == meeting.consent_session_id
                )
            )
        )
    return {
        "id": meeting.id,
        "consent_session_id": meeting.consent_session_id,
        "title": meeting.title,
        "platform": meeting.platform,
        "status": meeting.status,
        "provider_status": meeting.provider_status,
        "created_at": meeting.created_at,
        "joined_at": meeting.joined_at,
        "ended_at": meeting.ended_at,
        "last_synced_at": meeting.last_synced_at,
        "duration_seconds": duration,
        "media_recording_enabled": meeting.media_recording_enabled,
        "media_retention_days": meeting.media_retention_days,
        "media_available": bool(
            meeting.provider_recording_id
            and meeting.provider_media_id
            and not meeting.provider_deleted_at
        ),
        "media_type": meeting.media_type,
        "media_expires_at": meeting.media_expires_at,
        "transcript": meeting.transcript,
        "segments": segments,
        "report": report,
        "participants": [
            {
                "name": item.name,
                "email": item.email,
                "active": bool(item.consented_at and not item.withdrawn_at),
            }
            for item in participants
            if item.email
        ],
        "skills": public_skills(),
        "provider_data_deleted": bool(meeting.provider_deleted_at),
        "provider_cleanup_error": meeting.provider_cleanup_error,
        "welcome_posted": bool(meeting.welcome_posted_at),
        "recap_posted": bool(meeting.recap_posted_at),
        "chat_error": meeting.chat_error,
        "error": meeting.error,
    }


def launch_remote_meeting(
    consent: ConsentSession,
    user: User,
    meeting_url: str,
    language: str,
    db: Session,
) -> RemoteMeeting:
    """Lance Vexa une seule fois pour une session de consentement autorisée."""
    existing = db.exec(
        select(RemoteMeeting).where(RemoteMeeting.consent_session_id == consent.id)
    ).first()
    if existing and existing.status != RemoteMeetingStatus.FAILED:
        return existing
    platform, native_id, _ = vexa.parse_url(meeting_url)
    safe_url = (
        f"https://meet.google.com/{native_id}"
        if platform == "google_meet"
        else f"https://teams.live.com/meet/{native_id}"
    )
    meeting = existing or RemoteMeeting(
        owner_id=user.id,
        consent_session_id=consent.id,
        title=consent.title,
        meeting_url=safe_url,
        platform=platform,
        native_id=native_id,
        language=language,
        bot_name=settings.vexa_bot_name,
        media_recording_enabled=consent.media_recording_enabled,
        media_retention_days=consent.media_retention_days,
    )
    meeting.status = RemoteMeetingStatus.JOINING
    meeting.error = None
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    try:
        vexa.send_bot(meeting_url, language, consent.media_recording_enabled)
    except vexa.VexaError as exc:
        meeting.status = RemoteMeetingStatus.FAILED
        meeting.error = str(exc)
        db.add(meeting)
        db.commit()
        raise
    meeting.joined_at = utc_now()
    meeting.provider_status = "requested"
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    watch_remote_meeting(meeting.id)
    return meeting


@router.post("/remote-meetings", status_code=201)
def create_remote_meeting(
    payload: RemoteMeetingInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    if not settings.vexa_configured:
        raise HTTPException(503, "Configurez VEXA_API_KEY avant d'envoyer le bot")
    consent = db.get(ConsentSession, payload.consent_session_id)
    if not consent or consent.owner_id != user.id:
        raise HTTPException(404, "Réunion de consentement introuvable")
    participants = participants_for(consent.id, db)
    if consent.status != ConsentSessionStatus.RECORDING or not participants:
        raise HTTPException(409, "Le consentement de la réunion n'est pas actif")
    if not all(is_active(item) for item in participants):
        raise HTTPException(409, "Tous les participants doivent encore être d'accord")
    try:
        meeting = launch_remote_meeting(
            consent,
            user,
            payload.meeting_url,
            payload.language,
            db,
        )
    except vexa.VexaError as exc:
        raise HTTPException(502, str(exc)) from exc
    return remote_detail(meeting)


@router.get("/remote-meetings")
def list_remote_meetings(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meetings = db.exec(
        select(RemoteMeeting)
        .where(RemoteMeeting.owner_id == user.id)
        .order_by(RemoteMeeting.created_at.desc())
    )
    return [remote_detail(item) for item in meetings]


@router.get("/remote-meetings/{meeting_id}")
def get_remote_meeting(
    meeting_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    report = json.loads(meeting.report_json or "{}")
    if meeting.status == RemoteMeetingStatus.COMPLETED and meeting.platform == "google_meet":
        with suppress(Exception):
            refreshed = google_meet_context(meeting, db)
            if refreshed.get("participants"):
                report["provider_artifacts"] = refreshed
                meeting.report_json = json.dumps(report, ensure_ascii=False)
                db.add(meeting)
                db.commit()
                db.refresh(meeting)
    return remote_detail(meeting)


@router.get("/remote-meetings/{meeting_id}/media-access")
def get_remote_meeting_media_access(
    meeting_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    if not meeting.provider_recording_id or not meeting.provider_media_id:
        raise HTTPException(404, "Aucun média n'a été conservé pour cette réunion")
    expires_at = meeting.media_expires_at
    if expires_at and expires_at.replace(tzinfo=expires_at.tzinfo or UTC) <= utc_now():
        raise HTTPException(410, "La durée de conservation du replay est terminée")
    token = jwt.encode(
        {
            "sub": meeting.owner_id,
            "meeting": meeting.id,
            "scope": "meeting_media",
            "exp": utc_now() + timedelta(hours=2),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    base = settings.api_public_url.rstrip("/")
    return {
        "url": f"{base}/api/remote-meetings/{meeting.id}/media?access={token}",
        "expires_in": 7200,
    }


@router.get("/remote-meetings/{meeting_id}/media")
def get_remote_meeting_media(
    meeting_id: str,
    access: str,
    request: Request,
    db: Session = Depends(get_session),
):
    try:
        claims = jwt.decode(access, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(401, "Lien de replay invalide ou expiré") from exc
    if claims.get("meeting") != meeting_id or claims.get("scope") != "meeting_media":
        raise HTTPException(403, "Ce lien ne donne pas accès à cette réunion")
    meeting = db.get(RemoteMeeting, meeting_id)
    if not meeting or meeting.owner_id != claims.get("sub"):
        raise HTTPException(404, "Réunion distante introuvable")
    if not meeting.provider_recording_id or not meeting.provider_media_id:
        raise HTTPException(404, "Aucun média n'a été conservé pour cette réunion")
    expires_at = meeting.media_expires_at
    if expires_at and expires_at.replace(tzinfo=expires_at.tzinfo or UTC) <= utc_now():
        raise HTTPException(410, "La durée de conservation du replay est terminée")
    try:
        client, response = vexa.recording_stream(
            meeting.provider_recording_id,
            meeting.provider_media_id,
            request.headers.get("range"),
        )
    except vexa.VexaError as exc:
        raise HTTPException(502, str(exc)) from exc

    def body():
        try:
            yield from response.iter_bytes()
        finally:
            response.close()
            client.close()

    forwarded = {
        name: value
        for name in ("content-length", "content-range", "accept-ranges")
        if (value := response.headers.get(name))
    }
    media_type = response.headers.get("content-type") or (
        f"{meeting.media_type or 'audio'}/{meeting.media_format or 'webm'}"
    )
    return StreamingResponse(
        body(),
        status_code=response.status_code,
        media_type=media_type,
        headers=forwarded,
    )


@router.post("/remote-meetings/{meeting_id}/sync")
def sync_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    warning = None
    if meeting.status not in {
        RemoteMeetingStatus.COMPLETED,
        RemoteMeetingStatus.FAILED,
        RemoteMeetingStatus.STOPPED,
    }:
        try:
            if sync_remote_meeting(meeting.id):
                background_tasks.add_task(finalize_remote_meeting, meeting.id)
        except vexa.VexaError as exc:
            warning = str(exc)
    db.expire_all()
    result = remote_detail(owned_remote(meeting_id, user, db))
    result["sync_warning"] = warning
    return result


@router.post("/remote-meetings/{meeting_id}/finish", status_code=202)
def finish_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    if meeting.status in {RemoteMeetingStatus.COMPLETED, RemoteMeetingStatus.STOPPED}:
        return remote_detail(meeting)
    meeting.status = RemoteMeetingStatus.FINALIZING
    db.add(meeting)
    db.commit()
    background_tasks.add_task(finalize_remote_meeting, meeting.id)
    return remote_detail(meeting)


@router.post("/remote-meetings/{meeting_id}/stop")
def stop_meeting_now(
    meeting_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    """Retire immédiatement le bot et efface le direct sans lancer d'analyse."""
    meeting = owned_remote(meeting_id, user, db)
    if meeting.status not in {RemoteMeetingStatus.COMPLETED, RemoteMeetingStatus.STOPPED}:
        stop_and_erase_remote_meeting(meeting.id)
    db.expire_all()
    return remote_detail(owned_remote(meeting_id, user, db))


@router.post("/remote-meetings/{meeting_id}/podcast")
def create_podcast_overview(
    meeting_id: str,
    payload: PodcastInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    if meeting.status != RemoteMeetingStatus.COMPLETED or not meeting.report_json:
        raise HTTPException(409, "Le compte rendu doit être terminé avant le brief audio")
    segments = json.loads(meeting.segments_json or "[]")
    report = json.loads(meeting.report_json)
    try:
        overview = generate_podcast(
            report,
            segments,
            payload.format,
            payload.minutes,
            payload.focus,
        )
    except SummaryError as exc:
        raise HTTPException(502, str(exc)) from exc
    report["podcast_overview"] = overview.model_dump()
    report["podcast_script"] = report["podcast_overview"]["turns"]
    meeting.report_json = json.dumps(report, ensure_ascii=False)
    db.add(meeting)
    db.commit()
    return report["podcast_overview"]


@router.post("/remote-meetings/{meeting_id}/reanalyze", status_code=202)
def reanalyze_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    if not meeting.segments_json or meeting.segments_json == "[]":
        raise HTTPException(409, "Aucun transcript à réanalyser")
    meeting.status = RemoteMeetingStatus.FINALIZING
    meeting.error = None
    db.add(meeting)
    db.commit()
    background_tasks.add_task(reanalyze_remote_meeting, meeting.id)
    return remote_detail(meeting)


@router.put("/remote-meetings/{meeting_id}/actions/{action_index}")
def update_meeting_action(
    meeting_id: str,
    action_index: int,
    payload: ActionUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    report = json.loads(meeting.report_json or "{}")
    actions = report.get("actions") or []
    if action_index < 0 or action_index >= len(actions):
        raise HTTPException(404, "Action introuvable")
    participant = None
    if payload.owner_email:
        participant = db.exec(
            select(ParticipantConsent).where(
                ParticipantConsent.session_id == meeting.consent_session_id,
                ParticipantConsent.email == payload.owner_email.lower(),
            )
        ).first()
        if not participant or not participant.consented_at or participant.withdrawn_at:
            raise HTTPException(409, "Choisissez un participant consentant de cette réunion")
    action = actions[action_index]
    action["owner"] = participant.name if participant else None
    action["owner_email"] = participant.email if participant else None
    action["due_date"] = payload.due_date
    action["priority"] = payload.priority
    report.setdefault("manual_updates", []).append(
        {
            "section": "actions",
            "index": action_index,
            "updated_by": user.email,
            "updated_at": utc_now().isoformat(),
        }
    )
    meeting.report_json = json.dumps(report, ensure_ascii=False)
    db.add(meeting)
    db.commit()
    return action


@router.post("/remote-meetings/{meeting_id}/share")
def share_meeting_report(
    meeting_id: str,
    payload: ReportEmailInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    report = json.loads(meeting.report_json or "{}")
    if not report:
        raise HTTPException(409, "Le compte rendu n’est pas encore disponible")
    participants = list(
        db.exec(
            select(ParticipantConsent).where(
                ParticipantConsent.session_id == meeting.consent_session_id
            )
        )
    )
    allowed = {
        item.email.lower(): item
        for item in participants
        if item.consented_at and not item.withdrawn_at and item.email
    }
    requested = {item.lower() for item in payload.recipient_emails}
    if not requested <= allowed.keys():
        raise HTTPException(
            403,
            "Le compte rendu ne peut être envoyé qu’aux participants autorisés",
        )
    link = f"{settings.frontend_url.rstrip('/')}/meeting/{meeting.id}"
    failed = []
    for email in sorted(requested):
        participant = allowed[email]
        try:
            send_report_email(
                participant.name,
                participant.email,
                meeting.title,
                report.get("executive_summary") or "Le compte rendu est disponible.",
                link,
            )
        except EmailError:
            failed.append(email)
    if failed:
        raise HTTPException(502, f"Échec d’envoi pour : {', '.join(failed)}")
    return {"sent": len(requested)}


@router.post("/remote-meetings/{meeting_id}/follow-up", status_code=201)
def create_meeting_follow_up(
    meeting_id: str,
    payload: FollowUpInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    participants = list(
        db.exec(
            select(ParticipantConsent).where(
                ParticipantConsent.session_id == meeting.consent_session_id
            )
        )
    )
    allowed = {
        item.email.lower(): {"name": item.name, "email": item.email.lower()}
        for item in participants
        if item.consented_at and not item.withdrawn_at and item.email
    }
    requested = {item.lower() for item in payload.participant_emails}
    if not requested <= allowed.keys():
        raise HTTPException(403, "Invitez uniquement les participants autorisés de la réunion")
    query = select(CalendarConnection).where(
        CalendarConnection.user_id == user.id,
        CalendarConnection.active == True,  # noqa: E712
    )
    connections = list(db.exec(query))
    connection = next(
        (item for item in connections if item.id == payload.calendar_connection_id),
        connections[0] if connections else None,
    )
    if not connection:
        raise HTTPException(409, "Connectez un agenda avant de créer la réunion")
    from app.calendar_service import CalendarError, create_follow_up

    try:
        created = create_follow_up(
            connection,
            db,
            payload.title,
            payload.starts_at,
            payload.starts_at + timedelta(minutes=payload.duration_minutes),
            [allowed[email] for email in sorted(requested)],
        )
    except CalendarError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "provider": connection.provider,
        "event_id": created.get("id"),
        "meeting_url": created.get("hangoutLink")
        or (created.get("onlineMeeting") or {}).get("joinUrl"),
    }


@router.delete("/remote-meetings/{meeting_id}", status_code=204)
def delete_remote_meeting(
    meeting_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_remote(meeting_id, user, db)
    if not meeting.provider_deleted_at and settings.vexa_configured:
        with suppress(vexa.VexaError):
            vexa.stop_bot(meeting.platform, meeting.native_id)
        try:
            vexa.delete_meeting(meeting.platform, meeting.native_id)
        except vexa.VexaError as exc:
            raise HTTPException(502, str(exc)) from exc

    calendar_events = list(
        db.exec(select(CalendarEvent).where(CalendarEvent.remote_meeting_id == meeting.id))
    )
    participants = list(
        db.exec(
            select(ParticipantConsent).where(
                ParticipantConsent.session_id == meeting.consent_session_id
            )
        )
    )
    consent = db.get(ConsentSession, meeting.consent_session_id)

    for event in calendar_events:
        db.delete(event)
    for participant in participants:
        db.delete(participant)
    db.delete(meeting)
    db.flush()
    if consent:
        db.delete(consent)
    db.commit()


@router.get("/workspace/overview")
def workspace_overview(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    remote = list(db.exec(select(RemoteMeeting).where(RemoteMeeting.owner_id == user.id)))
    recordings = list(db.exec(select(Recording).where(Recording.owner_id == user.id)))
    reports = [json.loads(item.report_json) for item in remote if item.report_json]
    actions = [
        {**action, "meeting_id": item.id, "meeting_title": item.title}
        for item in remote
        if item.report_json
        for action in json.loads(item.report_json).get("actions", [])
    ]
    recent = sorted(
        [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status,
                "created_at": item.created_at,
                "source": "bot",
                "platform": item.platform,
            }
            for item in remote
        ]
        + [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status,
                "created_at": item.created_at,
                "source": "dictaphone",
                "platform": "in_person",
            }
            for item in recordings
        ],
        key=lambda item: item["created_at"],
        reverse=True,
    )[:6]
    return {
        "meetings": len(remote) + len(recordings),
        "live": sum(item.status == RemoteMeetingStatus.LIVE for item in remote),
        "decisions": sum(len(report.get("decisions", [])) for report in reports),
        "actions": actions,
        "captured_minutes": sum(item.duration_seconds for item in remote) // 60,
        "recent": recent,
    }
