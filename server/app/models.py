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


class RemoteMeetingStatus(str, enum.Enum):
    JOINING = "joining"
    LIVE = "live"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class CalendarProvider(str, enum.Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class CalendarEventStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


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


class CalendarConnection(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    provider: CalendarProvider = Field(index=True)
    account_email: str = Field(index=True)
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: str = ""
    active: bool = Field(default=True, index=True)
    auto_join_tagged: bool = True
    last_synced_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CalendarEvent(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    connection_id: str = Field(foreign_key="calendarconnection.id", index=True)
    provider_event_id: str = Field(index=True)
    title: str
    starts_at: datetime = Field(index=True)
    ends_at: datetime | None = None
    meeting_url: str
    organizer_email: str | None = None
    attendees_json: str = "[]"
    status: CalendarEventStatus = Field(default=CalendarEventStatus.SCHEDULED, index=True)
    auto_join: bool = Field(default=False, index=True)
    consent_session_id: str | None = Field(default=None, foreign_key="consentsession.id")
    remote_meeting_id: str | None = Field(default=None, foreign_key="remotemeeting.id")
    invitation_errors_json: str = "[]"
    bot_started_at: datetime | None = None
    last_synced_at: datetime = Field(default_factory=utc_now)


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
    media_recording_enabled: bool = False
    media_retention_days: int = 0
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
    podcast_json: str = "[]"
    generated_at: datetime = Field(default_factory=utc_now)


class RemoteMeeting(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    consent_session_id: str = Field(foreign_key="consentsession.id", index=True, unique=True)
    title: str
    meeting_url: str
    platform: str = Field(index=True)
    native_id: str = Field(index=True)
    language: str = "fr"
    bot_name: str = "Klaria — prise de notes"
    status: RemoteMeetingStatus = Field(default=RemoteMeetingStatus.JOINING, index=True)
    provider_status: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    joined_at: datetime | None = None
    ended_at: datetime | None = None
    last_synced_at: datetime | None = None
    duration_seconds: int = 0
    media_recording_enabled: bool = False
    media_retention_days: int = 0
    provider_recording_id: int | None = None
    provider_media_id: int | None = None
    media_type: str | None = None
    media_format: str | None = None
    media_expires_at: datetime | None = None
    transcript: str | None = None
    segments_json: str = "[]"
    report_json: str | None = None
    welcome_posted_at: datetime | None = None
    recap_posted_at: datetime | None = None
    chat_error: str | None = None
    provider_deleted_at: datetime | None = None
    provider_cleanup_error: str | None = None
    error: str | None = None


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
