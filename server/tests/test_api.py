from app.db import engine
from app.main import app
from app.models import ConsentSession, ConsentSessionStatus, ParticipantConsent
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel


def setup_function():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def register(client: TestClient, email: str = "user@example.com") -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password-123",
            "full_name": "Test User",
            "terms_accepted": True,
            "privacy_accepted": True,
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_profile():
    with TestClient(app) as client:
        token = register(client)
        profile = client.get("/api/auth/me", headers=auth(token))
        assert profile.status_code == 200
        assert profile.json()["email"] == "user@example.com"
        assert profile.json()["agreements_current"] is True

        login = client.post(
            "/api/auth/login",
            data={"username": "user@example.com", "password": "password-123"},
        )
        assert login.status_code == 200
        assert login.json()["token_type"] == "bearer"


def test_registration_is_not_created_without_legal_validation():
    with TestClient(app) as client:
        denied = client.post(
            "/api/auth/register",
            json={
                "email": "denied@example.com",
                "password": "password-123",
                "full_name": "Denied User",
                "terms_accepted": False,
                "privacy_accepted": True,
            },
        )
        assert denied.status_code == 400

        login = client.post(
            "/api/auth/login",
            data={"username": "denied@example.com", "password": "password-123"},
        )
        assert login.status_code == 401


def test_recording_requires_consent(monkeypatch):
    monkeypatch.setattr("app.routes.process_recording", lambda _: None)
    with TestClient(app) as client:
        token = register(client)
        denied = client.post(
            "/api/recordings",
            headers=auth(token),
            data={
                "title": "Test",
                "consent": "false",
                "consent_session_id": "missing",
            },
            files={"audio": ("sample.webm", b"audio-data", "audio/webm")},
        )
        assert denied.status_code == 400


def test_recordings_are_private_and_deletable(monkeypatch):
    monkeypatch.setattr("app.routes.process_recording", lambda _: None)
    with TestClient(app) as client:
        owner = register(client, "owner@example.com")
        stranger = register(client, "stranger@example.com")
        owner_id = client.get("/api/auth/me", headers=auth(owner)).json()["id"]
        with Session(engine) as session:
            meeting = ConsentSession(
                owner_id=owner_id,
                title="Point équipe",
                status=ConsentSessionStatus.RECORDING,
            )
            session.add(meeting)
            session.add(
                ParticipantConsent(
                    session_id=meeting.id,
                    name="Participant",
                    email="participant@example.com",
                    token_hash="test-token-hash",
                    notice_version="test",
                    consented_at=meeting.created_at,
                )
            )
            session.commit()
            meeting_id = meeting.id

        created = client.post(
            "/api/recordings",
            headers=auth(owner),
            data={
                "title": "Point équipe",
                "consent": "true",
                "consent_session_id": meeting_id,
            },
            files={"audio": ("sample.webm", b"audio-data", "audio/webm")},
        )
        assert created.status_code == 202
        assert created.json()["consent_version"]
        recording_id = created.json()["id"]
        assert (
            client.get(f"/api/recordings/{recording_id}", headers=auth(stranger)).status_code == 404
        )
        assert (
            client.delete(f"/api/recordings/{recording_id}", headers=auth(owner)).status_code == 204
        )


def test_consent_blocks_start_and_withdrawal_stops(monkeypatch):
    tokens = []
    monkeypatch.setattr("app.config.settings.smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.smtp_from_email", "scribe@example.com")
    monkeypatch.setattr(
        "app.consent_routes.send_consent_email",
        lambda _name, _email, _title, token: tokens.append(token),
    )
    with TestClient(app) as client:
        token = register(client)
        created = client.post(
            "/api/consent-sessions",
            headers=auth(token),
            json={
                "title": "Réunion RGPD",
                "participants": [{"name": "Yanis", "email": "yanis@example.com"}],
            },
        )
        meeting_id = created.json()["id"]
        blocked = client.post(
            f"/api/consent-sessions/{meeting_id}/start",
            headers=auth(token),
            json={"notice_confirmed": True},
        )
        assert blocked.status_code == 409

        client.post(f"/api/public/consents/{tokens[0]}/accept")
        started = client.post(
            f"/api/consent-sessions/{meeting_id}/start",
            headers=auth(token),
            json={"notice_confirmed": True},
        )
        assert started.json()["status"] == "recording"

        client.post(f"/api/public/consents/{tokens[0]}/withdraw")
        stopped = client.get(f"/api/consent-sessions/{meeting_id}", headers=auth(token))
        assert stopped.json()["status"] == "stopped"


def test_google_sso_reports_missing_configuration():
    with TestClient(app) as client:
        assert client.get("/api/auth/sso/google").status_code == 503
