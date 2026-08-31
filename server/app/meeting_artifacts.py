"""Présence officielle Google Meet, sans accéder aux enregistrements vidéo."""

import re
import unicodedata

import httpx
from sqlmodel import Session, select

from app.models import CalendarConnection, CalendarEvent, CalendarProvider, RemoteMeeting


class MeetArtifactError(RuntimeError):
    pass


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _get(url: str, token: str, **params) -> dict:
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MeetArtifactError("Google Meet n’a pas retourné ses données de réunion") from exc


def google_meet_context(meeting: RemoteMeeting, db: Session) -> dict:
    """Retourne uniquement la présence utile à l'attribution des voix."""
    from app.calendar_service import access_token

    empty = {"provider": meeting.platform, "participants": []}
    if meeting.platform != "google_meet":
        return empty
    event = db.exec(
        select(CalendarEvent).where(CalendarEvent.remote_meeting_id == meeting.id)
    ).first()
    if not event:
        return empty
    connection = db.get(CalendarConnection, event.connection_id)
    if not connection or connection.provider != CalendarProvider.GOOGLE:
        return empty

    token = access_token(connection, db)
    records = _get(
        "https://meet.googleapis.com/v2/conferenceRecords",
        token,
        filter=f'space.meeting_code = "{meeting.native_id}"',
        pageSize=10,
    ).get("conferenceRecords", [])
    if not records:
        return empty
    record = records[0]
    name = record["name"]
    people = _get(
        f"https://meet.googleapis.com/v2/{name}/participants",
        token,
        pageSize=250,
    ).get("participants", [])
    participants = []
    for person in people:
        identity = (
            person.get("signedinUser")
            or person.get("anonymousUser")
            or person.get("phoneUser")
            or {}
        )
        if identity.get("displayName"):
            participants.append(
                {
                    "display_name": identity["displayName"],
                    "joined_at": person.get("earliestStartTime"),
                    "left_at": person.get("latestEndTime"),
                }
            )
    return {
        "provider": "google_meet",
        "conference_started_at": record.get("startTime"),
        "conference_ended_at": record.get("endTime"),
        "participants": participants,
    }


def confirm_speaker_names(report: dict, participants: list[dict]) -> None:
    """Confirme uniquement une égalité exacte et unique entre plateforme et transcript."""
    normalized = {
        _plain(item["display_name"]): item["display_name"]
        for item in participants
        if item.get("display_name")
    }
    for speaker in report.get("speakers", []):
        if match := normalized.get(_plain(speaker.get("label", ""))):
            speaker["participant_name"] = match
            speaker["confidence"] = "platform"


def report_quality(report: dict, segments: list[dict]) -> dict:
    covered = {item.get("segment_id") for item in report.get("coverage", [])}
    known = sum(
        item.get("confidence") in {"platform", "explicit"}
        for item in report.get("speakers", [])
    )
    speakers = len(report.get("speakers", []))
    sections = ("key_points", "mentions", "decisions", "actions", "open_questions", "risks")
    facts = [item for key in sections for item in report.get(key, [])]
    return {
        "coverage_percent": round(100 * len(covered) / max(1, len(segments))),
        "identified_speakers_percent": round(100 * known / max(1, speakers)),
        "source_linked_facts_percent": round(
            100 * sum(bool(item.get("segment_ids")) for item in facts) / max(1, len(facts))
        ),
    }
