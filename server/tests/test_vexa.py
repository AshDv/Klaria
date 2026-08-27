import pytest
from app import vexa


def test_parses_teams_numeric_id_and_passcode():
    assert vexa.parse_url("https://teams.live.com/meet/1234567890123?p=AbC123") == (
        "teams",
        "1234567890123",
        "AbC123",
    )


def test_rejects_teams_link_without_numeric_id():
    with pytest.raises(vexa.VexaError, match="/meet/<ID>"):
        vexa.parse_url("https://teams.microsoft.com/l/meetup-join/example")


def test_sends_the_original_teams_url(monkeypatch):
    url = "https://teams.live.com/meet/1234567890123?p=AbC123"
    captured = {}

    class Response:
        status_code = 201

    def post(*_args, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(vexa.httpx, "post", post)
    monkeypatch.setattr(vexa.settings, "vexa_api_key", "test-key")

    assert vexa.send_bot(url) == ("teams", "1234567890123")
    assert captured["meeting_url"] == url
    assert captured["passcode"] == "AbC123"


def test_normalizes_epoch_times_and_mutable_duplicates():
    data = {
        "segments": [
            {
                "start_time": 1786366637.152,
                "end_time": 0,
                "absolute_start_time": "2026-08-10T10:00:00Z",
                "absolute_end_time": "2026-08-10T10:00:01Z",
                "speaker": "Speaker",
                "text": "Donc, Fabrice.",
                "completed": False,
            },
            {
                "start_time": 1786366637.152,
                "end_time": 0,
                "absolute_start_time": "2026-08-10T10:00:00Z",
                "absolute_end_time": "2026-08-10T10:00:03Z",
                "speaker": "Speaker",
                "text": "Donc, Fabrice, comment ça va, Fabrice ?",
                "completed": True,
            },
            {
                "absolute_start_time": "2026-08-10T10:00:05Z",
                "absolute_end_time": "2026-08-10T10:00:07Z",
                "speaker": "Speaker 2",
                "text": "Très bien, merci.",
            },
        ]
    }

    segments = vexa.normalize_segments(data)

    assert len(segments) == 2
    assert segments[0]["text"] == "Donc, Fabrice, comment ça va, Fabrice ?"
    assert segments[0]["start"] == 0
    assert segments[0]["end"] == 3
    assert segments[1]["start"] == 5
    assert segments[1]["end"] == 7


def test_keeps_a_real_repetition_at_a_later_time():
    data = {
        "segments": [
            {"start_time": 1, "end_time": 2, "speaker": "A", "text": "D'accord."},
            {"start_time": 10, "end_time": 11, "speaker": "A", "text": "D'accord."},
        ]
    }

    assert len(vexa.normalize_segments(data)) == 2


def test_replaces_same_provider_segment_even_if_timestamp_moves():
    data = {
        "segments": [
            {
                "segment_id": "fixed-id",
                "start_time": 2,
                "end_time": 3,
                "speaker": "A",
                "text": "Nous allons",
                "completed": False,
            },
            {
                "segment_id": "fixed-id",
                "start_time": 5,
                "end_time": 8,
                "speaker": "A",
                "text": "Nous allons livrer vendredi.",
                "completed": True,
            },
        ]
    }

    segments = vexa.normalize_segments(data)
    assert len(segments) == 1
    assert segments[0]["text"] == "Nous allons livrer vendredi."
