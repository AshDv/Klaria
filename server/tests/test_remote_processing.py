from app.remote_processing import _join_failure_message, is_stop_command


def test_explains_teams_auth_redirect():
    data = {"data": {"last_error": {"reason": "TeamsJoinRedirectError: teams_auth_redirect"}}}

    message = _join_failure_message(data)

    assert "page de connexion" in message
    assert "participants anonymes" in message


def test_understands_stop_command_with_spacing_and_case():
    assert is_stop_command("  STOP   SCRIBE  ")
    assert is_stop_command("Merci d'arrête scribe maintenant")
    assert not is_stop_command("Scribe peut continuer")
