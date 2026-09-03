"""Purge des résultats arrivés à expiration."""

import asyncio
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import (
    CalendarEvent,
    ConsentSession,
    ParticipantConsent,
    Recording,
    RemoteMeeting,
    SessionRecording,
    StructuredReport,
    utc_now,
)
from app.remote_processing import erase_provider_meeting


def purge_expired_data() -> None:
    now = utc_now()
    cutoff = now - timedelta(days=settings.result_retention_days)
    with Session(engine) as session:
        expiring_media = session.exec(
            select(RemoteMeeting).where(RemoteMeeting.media_expires_at < now)
        )
        for remote in expiring_media:
            if settings.vexa_configured and not remote.provider_deleted_at:
                erase_provider_meeting(remote.platform, remote.native_id)
            remote.provider_deleted_at = now
            remote.provider_recording_id = None
            remote.provider_media_id = None
            session.add(remote)
        for event in session.exec(select(CalendarEvent).where(CalendarEvent.starts_at < cutoff)):
            session.delete(event)
        session.flush()
        for remote in session.exec(select(RemoteMeeting).where(RemoteMeeting.created_at < cutoff)):
            if settings.vexa_configured and not remote.provider_deleted_at:
                erase_provider_meeting(remote.platform, remote.native_id)
            session.delete(remote)
        session.flush()
        recordings = session.exec(select(Recording).where(Recording.created_at < cutoff))
        for recording in recordings:
            link = session.exec(
                select(SessionRecording).where(SessionRecording.recording_id == recording.id)
            ).first()
            report = session.exec(
                select(StructuredReport).where(StructuredReport.recording_id == recording.id)
            ).first()
            if recording.audio_path:
                path = Path(recording.audio_path).resolve()
                if path.is_relative_to(settings.audio_directory) and path.exists():
                    path.unlink()
            if link:
                session.delete(link)
            if report:
                session.delete(report)
            session.flush()
            session.delete(recording)
        session.flush()
        meetings = session.exec(select(ConsentSession).where(ConsentSession.created_at < cutoff))
        for meeting in meetings:
            remaining_link = session.exec(
                select(SessionRecording).where(SessionRecording.session_id == meeting.id)
            ).first()
            if remaining_link:
                continue
            for consent in session.exec(
                select(ParticipantConsent).where(ParticipantConsent.session_id == meeting.id)
            ):
                session.delete(consent)
            session.flush()
            session.delete(meeting)
        session.commit()


async def retention_loop() -> None:
    """Contrôle les expirations chaque heure sans bloquer l'API."""
    while True:
        await asyncio.sleep(3600)
        await asyncio.to_thread(purge_expired_data)
