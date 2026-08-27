"""Synchronisation et analyse des réunions suivies par le bot."""

import json
import time
from contextlib import suppress
from datetime import timedelta

from sqlmodel import Session, select

from app import vexa
from app.config import settings
from app.db import engine
from app.llm import SummaryError, generate_summary
from app.meeting_artifacts import confirm_speaker_names, google_meet_context, report_quality
from app.models import (
    ConsentSession,
    ConsentSessionStatus,
    ParticipantConsent,
    RemoteMeeting,
    RemoteMeetingStatus,
    utc_now,
)

LIVE_STATES = {"active", "in_meeting", "recording", "transcribing"}
END_STATES = {"completed", "stopped", "ended"}
FAIL_STATES = {"failed", "rejected", "denied"}
STOP_COMMANDS = ("stop scribe", "arrête scribe", "arrete scribe", "retire scribe")


def _join_failure_message(data: dict) -> str:
    reason = str(((data.get("data") or {}).get("last_error") or {}).get("reason") or "")
    if "teams_auth_redirect" in reason:
        return (
            "Microsoft a redirigé le bot vers une page de connexion avant le lobby. "
            "Réessayez avec le lien Teams complet contenant /meet/ et ?p=, ou utilisez "
            "un lien professionnel Teams qui autorise les participants anonymes."
        )
    return reason[:500] or "Le bot n'a pas pu rejoindre ou suivre la réunion."


def _purge_provider(meeting: RemoteMeeting) -> None:
    try:
        vexa.delete_meeting(meeting.platform, meeting.native_id)
        meeting.provider_deleted_at = utc_now()
        meeting.provider_cleanup_error = None
    except vexa.VexaError as exc:
        meeting.provider_cleanup_error = str(exc)


def _store_transcript(meeting: RemoteMeeting, data: dict) -> list[dict]:
    segments = vexa.normalize_segments(data)
    if segments:
        meeting.segments_json = json.dumps(segments, ensure_ascii=False)
        meeting.transcript = vexa.transcript_text(data)
        meeting.duration_seconds = int(max(item["end"] for item in segments))
    meeting.provider_status = str(data.get("status") or meeting.provider_status or "unknown")
    meeting.last_synced_at = utc_now()
    return segments


def _store_provider_media(meeting: RemoteMeeting, provider_data: dict) -> None:
    if not meeting.media_recording_enabled or not provider_data.get("id"):
        return
    result = vexa.recording_for_meeting(int(provider_data["id"]))
    if not result:
        return
    recording, media = result["recording"], result["media"]
    meeting.provider_recording_id = int(recording["id"])
    meeting.provider_media_id = int(media["id"])
    meeting.media_type = str(media.get("type") or "audio")
    meeting.media_format = str(media.get("format") or "webm")
    meeting.media_expires_at = utc_now() + timedelta(
        days=max(1, meeting.media_retention_days)
    )


def is_stop_command(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return any(command in normalized for command in STOP_COMMANDS)


def _stop_requested(messages: list[dict]) -> bool:
    return any(
        isinstance(item, dict)
        and is_stop_command(str(item.get("text") or ""))
        for item in messages
    )


def _welcome_message() -> str:
    return (
        "Scribe est présent et transcrit cette réunion avec l'accord des participants. "
        "Écrivez « STOP SCRIBE » dans ce chat pour demander l'arrêt immédiat."
    )


def _recap_message(meeting: RemoteMeeting, report) -> str:
    actions = [item.task for item in report.actions[:3]]
    action_text = "\n".join(f"• {item}" for item in actions)
    link = f"{settings.frontend_url.rstrip('/')}/meeting/{meeting.id}"
    message = f"Compte rendu Scribe prêt\n\n{report.executive_summary}"
    if action_text:
        message += f"\n\nActions principales :\n{action_text}"
    return f"{message[:1600]}\n\nConsulter le compte rendu : {link}"


def _erase_after_chat_stop(meeting: RemoteMeeting) -> None:
    with suppress(vexa.VexaError):
        vexa.stop_bot(meeting.platform, meeting.native_id)
    _purge_provider(meeting)
    meeting.status = RemoteMeetingStatus.STOPPED
    meeting.ended_at = utc_now()
    meeting.transcript = None
    meeting.segments_json = "[]"
    meeting.report_json = None
    meeting.error = "Arrêt demandé dans le chat. Les données de la réunion ont été effacées."


def sync_remote_meeting(meeting_id: str) -> bool:
    """Met à jour le direct et indique si l'analyse finale doit démarrer."""
    with Session(engine) as db:
        meeting = db.get(RemoteMeeting, meeting_id)
        if not meeting or meeting.status in {
            RemoteMeetingStatus.COMPLETED,
            RemoteMeetingStatus.FAILED,
            RemoteMeetingStatus.STOPPED,
        }:
            return False
        data = vexa.get_transcript(meeting.platform, meeting.native_id)
        _store_transcript(meeting, data)
        provider_status = (meeting.provider_status or "").lower()
        if provider_status in LIVE_STATES:
            try:
                messages = vexa.get_chat(meeting.platform, meeting.native_id)
                if _stop_requested(messages):
                    _erase_after_chat_stop(meeting)
                    db.add(meeting)
                    db.commit()
                    return False
                if not meeting.welcome_posted_at:
                    vexa.send_chat(meeting.platform, meeting.native_id, _welcome_message())
                    meeting.welcome_posted_at = utc_now()
                    meeting.chat_error = None
            except vexa.VexaError as exc:
                meeting.chat_error = str(exc)
        should_finalize = provider_status in END_STATES
        if provider_status in FAIL_STATES:
            meeting.status = RemoteMeetingStatus.FAILED
            meeting.error = _join_failure_message(data)
        elif should_finalize:
            meeting.status = RemoteMeetingStatus.FINALIZING
        elif provider_status in LIVE_STATES or meeting.transcript:
            meeting.status = RemoteMeetingStatus.LIVE
        db.add(meeting)
        db.commit()
        return should_finalize


def finalize_remote_meeting(meeting_id: str) -> None:
    """Récupère la fin du transcript, produit le rapport puis purge Vexa."""
    with Session(engine) as db:
        meeting = db.get(RemoteMeeting, meeting_id)
        if not meeting or meeting.status == RemoteMeetingStatus.COMPLETED:
            return
        meeting.status = RemoteMeetingStatus.FINALIZING
        meeting.error = None
        db.add(meeting)
        db.commit()
        segments = json.loads(meeting.segments_json or "[]")
        provider_data: dict = {}
        for attempt in range(5):
            try:
                provider_data = vexa.get_transcript(meeting.platform, meeting.native_id)
                segments = _store_transcript(meeting, provider_data) or segments
                db.add(meeting)
                db.commit()
            except vexa.VexaError:
                pass
            if segments or attempt == 4:
                break
            time.sleep(2)

        if not segments or not meeting.transcript:
            meeting.status = RemoteMeetingStatus.FAILED
            meeting.error = (
                "Aucune parole n'a été transcrite. Vérifiez que l'hôte a admis Scribe "
                "et qu'un participant a parlé."
            )
            meeting.ended_at = utc_now()
            with suppress(vexa.VexaError):
                vexa.stop_bot(meeting.platform, meeting.native_id)
            _purge_provider(meeting)
            db.add(meeting)
            db.commit()
            return

        consent = db.get(ConsentSession, meeting.consent_session_id)
        participants = list(
            db.exec(
                select(ParticipantConsent).where(
                    ParticipantConsent.session_id == meeting.consent_session_id
                )
            )
        )
        names = [item.name for item in participants if item.name]
        try:
            report = generate_summary(meeting.transcript, segments, names)
        except SummaryError as exc:
            meeting.status = RemoteMeetingStatus.FAILED
            meeting.error = str(exc)
            meeting.ended_at = utc_now()
            with suppress(vexa.VexaError):
                vexa.stop_bot(meeting.platform, meeting.native_id)
            _purge_provider(meeting)
            db.add(meeting)
            db.commit()
            return

        try:
            vexa.send_chat(
                meeting.platform,
                meeting.native_id,
                _recap_message(meeting, report),
            )
            meeting.recap_posted_at = utc_now()
            meeting.chat_error = None
        except vexa.VexaError as exc:
            meeting.chat_error = str(exc)
        finally:
            with suppress(vexa.VexaError):
                vexa.stop_bot(meeting.platform, meeting.native_id)

        if meeting.media_recording_enabled:
            for attempt in range(5):
                with suppress(vexa.VexaError):
                    _store_provider_media(meeting, provider_data)
                if meeting.provider_media_id or attempt == 4:
                    break
                time.sleep(1)

        report_data = report.model_dump()
        artifacts = {"provider": meeting.platform, "participants": [], "recordings": []}
        with suppress(Exception):
            artifacts = google_meet_context(meeting, db)
        confirm_speaker_names(report_data, artifacts.get("participants", []))
        report_data["provider_artifacts"] = artifacts
        report_data["quality"] = report_quality(report_data, segments)
        meeting.report_json = json.dumps(report_data, ensure_ascii=False)
        meeting.status = RemoteMeetingStatus.COMPLETED
        meeting.ended_at = utc_now()
        if consent:
            consent.status = ConsentSessionStatus.STOPPED
            consent.stopped_at = meeting.ended_at
            db.add(consent)
        db.add(meeting)
        db.commit()

        if not meeting.media_recording_enabled or not meeting.provider_media_id:
            _purge_provider(meeting)
            db.add(meeting)
            db.commit()


def reanalyze_remote_meeting(meeting_id: str) -> None:
    """Nettoie un ancien transcript puis régénère le rapport sans rappeler Vexa."""
    with Session(engine) as db:
        meeting = db.get(RemoteMeeting, meeting_id)
        if not meeting:
            return
        segments = vexa.normalize_segments(
            {"segments": json.loads(meeting.segments_json or "[]")}
        )
        if not segments:
            meeting.status = RemoteMeetingStatus.FAILED
            meeting.error = "Aucun passage exploitable à réanalyser."
            db.add(meeting)
            db.commit()
            return
        participants = list(
            db.exec(
                select(ParticipantConsent).where(
                    ParticipantConsent.session_id == meeting.consent_session_id
                )
            )
        )
        meeting.segments_json = json.dumps(segments, ensure_ascii=False)
        meeting.transcript = "\n".join(
            f"{item['speaker']}: {item['text']}" for item in segments
        )
        meeting.duration_seconds = int(max(item["end"] for item in segments))
        try:
            report = generate_summary(
                meeting.transcript,
                segments,
                [item.name for item in participants if item.name],
            )
        except SummaryError as exc:
            meeting.status = RemoteMeetingStatus.FAILED
            meeting.error = str(exc)
        else:
            previous = json.loads(meeting.report_json or "{}")
            report_data = report.model_dump()
            report_data["provider_artifacts"] = previous.get(
                "provider_artifacts",
                {"provider": meeting.platform, "participants": [], "recordings": []},
            )
            confirm_speaker_names(
                report_data,
                report_data["provider_artifacts"].get("participants", []),
            )
            report_data["quality"] = report_quality(report_data, segments)
            meeting.report_json = json.dumps(report_data, ensure_ascii=False)
            meeting.status = RemoteMeetingStatus.COMPLETED
            meeting.error = None
        db.add(meeting)
        db.commit()


def stop_and_erase_remote_meeting(meeting_id: str) -> None:
    """Applique immédiatement un retrait de consentement."""
    with Session(engine) as db:
        meeting = db.get(RemoteMeeting, meeting_id)
        if not meeting:
            return
        with suppress(vexa.VexaError):
            vexa.stop_bot(meeting.platform, meeting.native_id)
        _purge_provider(meeting)
        meeting.status = RemoteMeetingStatus.STOPPED
        meeting.ended_at = utc_now()
        meeting.transcript = None
        meeting.segments_json = "[]"
        meeting.report_json = None
        meeting.error = "Traitement arrêté et données effacées après retrait du consentement."
        db.add(meeting)
        db.commit()


def erase_provider_meeting(platform: str, native_id: str) -> None:
    """Supprime chez Vexa sans dépendre d'une ligne locale encore présente."""
    with suppress(vexa.VexaError):
        vexa.stop_bot(platform, native_id)
    with suppress(vexa.VexaError):
        vexa.delete_meeting(platform, native_id)


def provider_ready() -> bool:
    return settings.vexa_configured
