"""Consentement individuel préalable, révocable et prouvable."""

import hashlib
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.emailing import EmailError, send_consent_email
from app.models import (
    ConsentSession,
    ConsentSessionStatus,
    ParticipantConsent,
    Recording,
    SessionRecording,
    StructuredReport,
    User,
    utc_now,
)

router = APIRouter(prefix="/api")


class ParticipantInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class SessionInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    scheduled_at: datetime | None = None
    participants: list[ParticipantInput] = Field(min_length=1, max_length=30)


class StartInput(BaseModel):
    notice_confirmed: bool


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def owned_session(session_id: str, user: User, db: Session) -> ConsentSession:
    meeting = db.get(ConsentSession, session_id)
    if not meeting or meeting.owner_id != user.id:
        raise HTTPException(404, "Réunion introuvable")
    return meeting


def participants_for(session_id: str, db: Session) -> list[ParticipantConsent]:
    return list(
        db.exec(select(ParticipantConsent).where(ParticipantConsent.session_id == session_id))
    )


def is_active(consent: ParticipantConsent) -> bool:
    return bool(consent.consented_at and not consent.withdrawn_at)


def refresh_status(meeting: ConsentSession, db: Session) -> None:
    participants = participants_for(meeting.id, db)
    if meeting.status != ConsentSessionStatus.RECORDING:
        meeting.status = (
            ConsentSessionStatus.READY
            if participants and all(is_active(item) for item in participants)
            else ConsentSessionStatus.PENDING
        )
    db.add(meeting)


def session_detail(meeting: ConsentSession, db: Session) -> dict:
    participants = participants_for(meeting.id, db)
    return {
        "id": meeting.id,
        "title": meeting.title,
        "scheduled_at": meeting.scheduled_at,
        "status": meeting.status,
        "notice_confirmed_at": meeting.notice_confirmed_at,
        "all_consented": bool(participants) and all(is_active(item) for item in participants),
        "participants": [
            {
                "id": item.id,
                "name": item.name,
                "email": item.email,
                "consented_at": item.consented_at,
                "withdrawn_at": item.withdrawn_at,
            }
            for item in participants
        ],
    }


@router.post("/consent-sessions", status_code=201)
def create_session(
    payload: SessionInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    if not settings.smtp_configured:
        raise HTTPException(503, "Configurez SMTP avant d’inviter les participants")
    emails = [str(item.email).lower() for item in payload.participants]
    if len(emails) != len(set(emails)):
        raise HTTPException(400, "Chaque participant doit avoir une adresse unique")

    meeting = ConsentSession(
        owner_id=user.id,
        title=payload.title.strip(),
        scheduled_at=payload.scheduled_at,
    )
    db.add(meeting)
    deliveries: list[tuple[ParticipantInput, str]] = []
    for item in payload.participants:
        token = secrets.token_urlsafe(32)
        db.add(
            ParticipantConsent(
                session_id=meeting.id,
                name=item.name.strip(),
                email=str(item.email).lower(),
                token_hash=token_hash(token),
                notice_version=settings.privacy_version,
            )
        )
        deliveries.append((item, token))
    db.commit()

    failed: list[str] = []
    for item, token in deliveries:
        try:
            send_consent_email(item.name, str(item.email), meeting.title, token)
        except EmailError:
            failed.append(str(item.email))
    result = session_detail(meeting, db)
    result["delivery_errors"] = failed
    return result


@router.get("/consent-sessions")
def list_sessions(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meetings = db.exec(
        select(ConsentSession)
        .where(ConsentSession.owner_id == user.id)
        .order_by(ConsentSession.created_at.desc())
    )
    return [session_detail(item, db) for item in meetings]


@router.get("/consent-sessions/{session_id}")
def get_consent_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    return session_detail(owned_session(session_id, user, db), db)


@router.post("/consent-sessions/{session_id}/start")
def start_session(
    session_id: str,
    payload: StartInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_session(session_id, user, db)
    if not payload.notice_confirmed:
        raise HTTPException(400, "Annoncez l’enregistrement aux personnes présentes")
    participants = participants_for(meeting.id, db)
    if not participants or not all(is_active(item) for item in participants):
        raise HTTPException(409, "Tous les participants n’ont pas encore consenti")
    meeting.status = ConsentSessionStatus.RECORDING
    meeting.notice_confirmed_at = utc_now()
    meeting.started_at = utc_now()
    db.add(meeting)
    db.commit()
    return session_detail(meeting, db)


@router.post("/consent-sessions/{session_id}/stop")
def stop_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    meeting = owned_session(session_id, user, db)
    meeting.status = ConsentSessionStatus.STOPPED
    meeting.stopped_at = utc_now()
    db.add(meeting)
    db.commit()
    return session_detail(meeting, db)


def public_consent(token: str, db: Session) -> ParticipantConsent:
    consent = db.exec(
        select(ParticipantConsent).where(ParticipantConsent.token_hash == token_hash(token))
    ).first()
    if not consent:
        raise HTTPException(404, "Lien de consentement invalide")
    return consent


@router.get("/public/consents/{token}")
def get_public_consent(token: str, db: Session = Depends(get_session)):
    consent = public_consent(token, db)
    meeting = db.get(ConsentSession, consent.session_id)
    return {
        "participant_name": consent.name,
        "meeting_title": meeting.title if meeting else "Réunion",
        "consented_at": consent.consented_at,
        "withdrawn_at": consent.withdrawn_at,
        "notice_version": consent.notice_version,
        "processor": "Mistral AI",
        "privacy_contact": settings.privacy_contact_email,
        "retention_days": settings.result_retention_days,
    }


@router.post("/public/consents/{token}/accept")
def accept_consent(token: str, db: Session = Depends(get_session)):
    consent = public_consent(token, db)
    consent.consented_at = utc_now()
    consent.withdrawn_at = None
    meeting = db.get(ConsentSession, consent.session_id)
    db.add(consent)
    if meeting:
        refresh_status(meeting, db)
    db.commit()
    return {"status": "accepted", "consented_at": consent.consented_at}


@router.post("/public/consents/{token}/withdraw")
def withdraw_consent(token: str, db: Session = Depends(get_session)):
    consent = public_consent(token, db)
    consent.withdrawn_at = utc_now()
    meeting = db.get(ConsentSession, consent.session_id)
    if meeting:
        meeting.status = ConsentSessionStatus.STOPPED
        meeting.stopped_at = utc_now()
        db.add(meeting)
    db.add(consent)
    db.commit()
    return {"status": "withdrawn", "withdrawn_at": consent.withdrawn_at}


@router.delete("/public/consents/{token}/data", status_code=204)
def erase_consent_data(token: str, db: Session = Depends(get_session)):
    consent = public_consent(token, db)
    links = db.exec(
        select(SessionRecording).where(SessionRecording.session_id == consent.session_id)
    )
    for link in links:
        recording = db.get(Recording, link.recording_id)
        if recording:
            path = Path(recording.audio_path).resolve()
            if (
                recording.audio_path
                and path.is_relative_to(settings.audio_directory)
                and path.exists()
            ):
                path.unlink()
            report = db.exec(
                select(StructuredReport).where(StructuredReport.recording_id == recording.id)
            ).first()
            if report:
                db.delete(report)
            db.delete(recording)
        db.delete(link)
    consent.name = "Données effacées"
    consent.email = ""
    consent.token_hash = token_hash(secrets.token_urlsafe(32))
    consent.erasure_requested_at = utc_now()
    db.add(consent)
    db.commit()
