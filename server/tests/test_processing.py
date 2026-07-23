import json
from pathlib import Path

from app.db import engine
from app.llm import ActionItem, Coverage, Decision, MeetingSummary, Speaker
from app.models import Recording, RecordingStatus, StructuredReport, User
from app.processing import process_recording
from sqlmodel import Session, SQLModel, select


def test_processing_stores_report_and_removes_audio(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path))
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    audio = tmp_path / "sample.webm"
    audio.write_bytes(b"audio")
    with Session(engine) as session:
        user = User(
            email="process@example.com",
            full_name="Process",
            hashed_password="!test",
        )
        session.add(user)
        session.commit()
        recording = Recording(
            owner_id=user.id,
            title="Test",
            original_filename="sample.webm",
            content_type="audio/webm",
            audio_path=str(audio),
            consent_version="test",
        )
        session.add(recording)
        session.commit()
        recording_id = recording.id

    monkeypatch.setattr(
        "app.processing.transcribe_audio",
        lambda *_: {
            "text": "Une décision a été prise.",
            "segments": [
                {
                    "id": 0,
                    "start": 0,
                    "end": 2,
                    "speaker": "speaker_0",
                    "text": "Une décision a été prise.",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "app.processing.generate_summary",
        lambda *_: MeetingSummary(
            language="fr",
            executive_summary="La réunion aboutit à une décision.",
            detailed_minutes="Le projet est validé.",
            speakers=[Speaker(label="speaker_0", confidence="unknown")],
            key_points=[],
            decisions=[
                Decision(
                    decision="Valider le projet",
                    decided_by=["speaker_0"],
                    segment_ids=[0],
                )
            ],
            actions=[ActionItem(task="Préparer la suite", segment_ids=[0])],
            open_questions=[],
            risks=[],
            coverage=[
                Coverage(
                    segment_id=0,
                    classification="decision",
                    used_in=["decisions"],
                )
            ],
        ),
    )
    process_recording(recording_id)

    with Session(engine) as session:
        saved = session.get(Recording, recording_id)
        report = session.exec(
            select(StructuredReport).where(StructuredReport.recording_id == recording_id)
        ).first()
        assert saved.status == RecordingStatus.COMPLETED
        assert saved.transcript == "Une décision a été prise."
        assert json.loads(saved.decisions_json) == ["Valider le projet"]
        assert report and report.model
        assert not audio.exists()
