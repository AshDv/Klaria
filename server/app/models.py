"""Modèles de données du MVP dictaphone."""

import enum
import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class RecordingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsentSessionStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RECORDING = "recording"
    STOPPED = "stopped"


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str | None = None
    hashed_password: str
    created_at: datetime = Field(default_factory=utc_now)


class ExternalIdentity(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    provider: str = Field(index=True)
    subject: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)


class UserAgreement(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    terms_version: str
    privacy_version: str
    accepted_at: datetime = Field(default_factory=utc_now)


class ConsentSession(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    title: str
    scheduled_at: datetime | None = None
    status: ConsentSessionStatus = Field(
        default=ConsentSessionStatus.PENDING,
        index=True,
    )
    notice_confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None


class ParticipantConsent(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="consentsession.id", index=True)
    name: str
    email: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)
    notice_version: str
    invited_at: datetime = Field(default_factory=utc_now)
    consented_at: datetime | None = None
    withdrawn_at: datetime | None = None
    erasure_requested_at: datetime | None = None


class Recording(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    title: str
    original_filename: str
    content_type: str
    audio_path: str
    status: RecordingStatus = Field(default=RecordingStatus.UPLOADED, index=True)
    consent_version: str
    consent_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error: str | None = None
    transcript: str | None = None
    segments_json: str | None = None
    summary: str | None = None
    topics_json: str | None = None
    decisions_json: str | None = None
    actions_json: str | None = None


class SessionRecording(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str = Field(foreign_key="consentsession.id", index=True)
    recording_id: str = Field(foreign_key="recording.id", index=True, unique=True)


class StructuredReport(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    recording_id: str = Field(foreign_key="recording.id", index=True, unique=True)
    model: str
    language: str
    detailed_minutes: str
    speakers_json: str
    key_points_json: str
    decisions_json: str
    actions_json: str
    open_questions_json: str
    risks_json: str
    coverage_json: str
    generated_at: datetime = Field(default_factory=utc_now)


# Ancien modèle conservé pour que les bases de développement existantes restent lisibles.
class Meeting(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    title: str
    platform: str = "legacy"
    meeting_url: str = ""
    native_id: str | None = None
    status: str = "legacy"
    created_at: datetime = Field(default_factory=utc_now)
    duration_sec: int | None = None
    error: str | None = None
    transcript: str | None = None
    summary: str | None = None
    cr_md: str | None = None
    decisions_json: str | None = None
    actions_json: str | None = None
    key_points_json: str | None = None
    topics_json: str | None = None
    sentiment: str | None = None
