from app.remote_processing import (
    _join_failure_message,
    _stop_requested,
    _stop_segment_hint,
    is_stop_command,
)


def test_explains_teams_auth_redirect():
    data = {"data": {"last_error": {"reason": "TeamsJoinRedirectError: teams_auth_redirect"}}}

    message = _join_failure_message(data)

    assert "page de connexion" in message
    assert "participants anonymes" in message


def test_understands_stop_command_with_spacing_and_case():
    assert is_stop_command("  STOP   KLARIA  ")
    assert is_stop_command("Merci d'arrête klaria maintenant")
    assert not is_stop_command("Klaria peut continuer")


def test_ignores_the_bot_privacy_notice_but_accepts_a_participant_stop():
    messages = [
        {"sender_name": "Klaria", "text": "Klaria est présent. Écrivez STOP KLARIA."},
        {"from": {"displayName": "Yanis Zedira"}, "body": {"content": "STOP KLARIA"}},
    ]

    assert _stop_requested(messages)["from"]["displayName"] == "Yanis Zedira"


def test_detects_stop_command_from_transcript_when_chat_is_unavailable():
    segments = [{"speaker": "Yanis Zedira", "text": "stop klaria s'il te plaît"}]

    assert _stop_segment_hint(segments) == "Yanis Zedira"
