"""API Scribe."""

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
