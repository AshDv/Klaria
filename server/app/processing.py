"""Enchaînement Voxtral puis Mistral pour un enregistrement."""

import json
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.llm import SummaryError, generate_summary
from app.models import (
    ConsentSession,
    ConsentSessionStatus,
    ParticipantConsent,
    Recording,
    RecordingStatus,
    SessionRecording,
    StructuredReport,
    utc_now,
)
from app.transcription import TranscriptionError, transcribe_audio


def process_recording(recording_id: str) -> None:
    with Session(engine) as session:
        recording = session.get(Recording, recording_id)
        if not recording or recording.status == RecordingStatus.PROCESSING:
            return
        recording.status = RecordingStatus.PROCESSING
        recording.error = None
        session.add(recording)
        session.commit()

        path = Path(recording.audio_path).resolve()
        link = None
        try:
            link = session.exec(
                select(SessionRecording).where(SessionRecording.recording_id == recording.id)
            ).first()
            participants = (
                list(
                    session.exec(
                        select(ParticipantConsent).where(
                            ParticipantConsent.session_id == link.session_id
                        )
                    )
                )
                if link
                else []
            )
            names = [item.name for item in participants if item.name]
            transcript = transcribe_audio(path, recording.content_type, names)
            result = generate_summary(transcript["text"], transcript["segments"], names)
            recording.transcript = transcript["text"]
            recording.segments_json = json.dumps(transcript["segments"], ensure_ascii=False)
            recording.summary = result.executive_summary
            recording.topics_json = json.dumps(
                [item.topic for item in result.key_points],
                ensure_ascii=False,
            )
            recording.decisions_json = json.dumps(
                [item.decision for item in result.decisions],
                ensure_ascii=False,
            )
            recording.actions_json = json.dumps(
                [item.model_dump() for item in result.actions], ensure_ascii=False
            )
            session.add(
                StructuredReport(
                    recording_id=recording.id,
                    model=settings.summary_model,
                    language=result.language,
                    detailed_minutes=result.detailed_minutes,
                    speakers_json=json.dumps(
                        [item.model_dump() for item in result.speakers],
                        ensure_ascii=False,
                    ),
                    key_points_json=json.dumps(
                        [item.model_dump() for item in result.key_points],
                        ensure_ascii=False,
                    ),
                    decisions_json=json.dumps(
                        [item.model_dump() for item in result.decisions],
                        ensure_ascii=False,
                    ),
                    actions_json=json.dumps(
                        [item.model_dump() for item in result.actions],
                        ensure_ascii=False,
                    ),
                    open_questions_json=json.dumps(
                        [item.model_dump() for item in result.open_questions],
                        ensure_ascii=False,
                    ),
                    risks_json=json.dumps(
                        [item.model_dump() for item in result.risks],
                        ensure_ascii=False,
                    ),
                    coverage_json=json.dumps(
                        [item.model_dump() for item in result.coverage],
                        ensure_ascii=False,
                    ),
                )
            )
            recording.status = RecordingStatus.COMPLETED
            recording.completed_at = utc_now()
        except (TranscriptionError, SummaryError, OSError) as exc:
            recording.status = RecordingStatus.FAILED
            recording.error = str(exc)
        finally:
            if path.is_relative_to(settings.audio_directory) and path.exists():
                path.unlink()
            recording.audio_path = ""
            if link:
                meeting = session.get(ConsentSession, link.session_id)
                if meeting:
                    meeting.status = ConsentSessionStatus.STOPPED
                    meeting.stopped_at = utc_now()
                    session.add(meeting)
        session.add(recording)
        session.commit()
