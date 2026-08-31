from datetime import UTC, datetime

from app.calendar_service import (
    _google_item,
    _microsoft_item,
    calendar_event_detail,
    meeting_url,
)
from app.emailing import _date
from app.models import CalendarEvent


def test_google_event_extracts_meet_and_human_attendees():
    item = _google_item(
        {
            "id": "google-1",
            "summary": "[KLARIA] Revue",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "start": {"dateTime": "2026-08-14T09:00:00Z"},
            "end": {"dateTime": "2026-08-14T10:00:00Z"},
            "attendees": [
                {"email": "owner@example.com", "self": True},
                {"email": "guest@example.com", "displayName": "Invité"},
                {"email": "room@example.com", "resource": True},
            ],
        },
        "owner@example.com",
    )
    assert item["meeting_url"] == "https://meet.google.com/abc-defg-hij"
    assert item["attendees"] == [{"name": "Invité", "email": "guest@example.com"}]


def test_microsoft_event_extracts_teams_and_excludes_owner():
    item = _microsoft_item(
        {
            "id": "teams-1",
            "subject": "Comité",
            "start": {"dateTime": "2026-08-14T09:00:00+00:00"},
            "end": {"dateTime": "2026-08-14T10:00:00+00:00"},
            "onlineMeeting": {
                "joinUrl": "https://teams.microsoft.com/l/meetup-join/example"
            },
            "attendees": [
                {"emailAddress": {"address": "owner@example.com"}, "type": "required"},
                {
                    "emailAddress": {"address": "guest@example.com", "name": "Invité"},
                    "type": "required",
                },
            ],
        },
        "owner@example.com",
    )
    assert item["meeting_url"].startswith("https://teams.microsoft.com/")
    assert item["attendees"] == [{"name": "Invité", "email": "guest@example.com"}]


def test_meeting_url_ignores_unrelated_links():
    assert meeting_url("https://example.com") is None


def test_calendar_event_exposes_platform_for_the_interface():
    event = CalendarEvent(
        owner_id="owner",
        connection_id="connection",
        provider_event_id="event",
        title="Revue",
        starts_at=datetime.now(UTC),
        meeting_url="https://meet.google.com/abc-defg-hij",
    )
    assert calendar_event_detail(event)["platform"] == "google_meet"


def test_calendar_event_serializes_utc_and_email_displays_paris_time():
    event = CalendarEvent(
        owner_id="owner",
        connection_id="connection",
        provider_event_id="event-zone",
        title="Revue timezone",
        starts_at=datetime(2026, 8, 21, 8, 0, tzinfo=UTC),
        meeting_url="https://meet.google.com/abc-defg-hij",
    )
    assert calendar_event_detail(event)["starts_at"] == "2026-08-21T08:00:00+00:00"
    assert _date(event.starts_at) == "21/08/2026 à 10:00 (heure de Paris)"
