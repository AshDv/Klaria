from app.remote_processing import _join_failure_message, _stop_requested, is_stop_command


def test_explains_teams_auth_redirect():
    data = {"data": {"last_error": {"reason": "TeamsJoinRedirectError: teams_auth_redirect"}}}

    message = _join_failure_message(data)

    assert "page de connexion" in message
    assert "participants anonymes" in message


def test_understands_stop_command_with_spacing_and_case():
    assert is_stop_command("  STOP   NOLYA  ")
    assert is_stop_command("Merci d'arrête nolya maintenant")
    assert not is_stop_command("Nolya peut continuer")


def test_ignores_the_bot_privacy_notice_but_accepts_a_participant_stop():
    messages = [
        {"sender_name": "Nolya", "text": "Nolya est présent. Écrivez STOP NOLYA."},
        {"sender_name": "Yanis Zedira", "text": "STOP NOLYA"},
    ]

    assert _stop_requested(messages)["sender_name"] == "Yanis Zedira"
