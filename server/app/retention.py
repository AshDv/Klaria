"""Purge des résultats arrivés à expiration."""

from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import (
    ConsentSession,
    ParticipantConsent,
    Recording,
    SessionRecording,
    StructuredReport,
    utc_now,
)


def purge_expired_data() -> None:
    cutoff = utc_now() - timedelta(days=settings.result_retention_days)
    with Session(engine) as session:
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
            session.delete(recording)
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
            session.delete(meeting)
        session.commit()
