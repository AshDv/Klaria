"""API du MVP : comptes, SSO, dictaphone et résultats."""

import asyncio
import json
from pathlib import Path
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.auth import create_access_token, current_user, hash_password, verify_password
from app.config import settings
from app.db import get_session
from app.legal_routes import AgreementInput, has_current_agreements, save_agreements
from app.models import (
    ConsentSession,
    ConsentSessionStatus,
    ExternalIdentity,
    ParticipantConsent,
    Recording,
    SessionRecording,
    StructuredReport,
    User,
)
from app.processing import process_recording

router = APIRouter(prefix="/api")
oauth = OAuth()
if settings.google_sso_configured:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
if settings.microsoft_sso_configured:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url=(
            f"https://login.microsoftonline.com/{settings.microsoft_tenant}/v2.0/"
            ".well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile User.Read"},
    )

ALLOWED_AUDIO = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
}
CONSENT_VERSION = "2026-07-26"


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=72)
    full_name: str = Field(min_length=2, max_length=100)
    terms_accepted: bool
    privacy_accepted: bool


def token_response(user: User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


def sso_user(
    provider: str,
    subject: str,
    email: str,
    full_name: str | None,
    session: Session,
) -> User:
    """Lie une identité vérifiée sans dupliquer la création de compte."""
    identity = session.exec(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == provider,
            ExternalIdentity.subject == subject,
        )
    ).first()
    user = session.get(User, identity.user_id) if identity else None
    if user:
        return user
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(
            email=email,
            full_name=(full_name or email.split("@")[0]).strip(),
            hashed_password=f"!{provider}-sso",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    session.add(ExternalIdentity(user_id=user.id, provider=provider, subject=subject))
    session.commit()
    return user


def sso_redirect(user: User) -> RedirectResponse:
    access_token = quote(create_access_token(user.id), safe="")
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/#access_token={access_token}")


@router.post("/auth/register", status_code=201)
def register(payload: RegisterInput, session: Session = Depends(get_session)):
    agreement = AgreementInput(
        terms_accepted=payload.terms_accepted,
        privacy_accepted=payload.privacy_accepted,
    )
    if not agreement.terms_accepted or not agreement.privacy_accepted:
        raise HTTPException(400, "Les CGU et l’information RGPD doivent être validées")
    email = payload.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "Cette adresse e-mail est déjà utilisée")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    save_agreements(user.id, agreement, session)
    return token_response(user)


@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form.username.lower())).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect")
    return token_response(user)


@router.get("/auth/sso/google")
async def google_login(request: Request):
    if not settings.google_sso_configured:
        raise HTTPException(503, "La connexion Google n’est pas encore configurée")
    callback = f"{settings.api_public_url.rstrip('/')}/api/auth/sso/google/callback"
    return await oauth.google.authorize_redirect(request, callback)


@router.get("/auth/sso/google/callback")
async def google_callback(request: Request, session: Session = Depends(get_session)):
    if not settings.google_sso_configured:
        raise HTTPException(503, "La connexion Google n’est pas configurée")
    try:
        token = await oauth.google.authorize_access_token(request)
        profile = token.get("userinfo") or await oauth.google.userinfo(token=token)
    except OAuthError as exc:
        raise HTTPException(400, "La connexion Google a échoué") from exc
    if not profile.get("email") or profile.get("email_verified") is False:
        raise HTTPException(400, "Google n’a pas confirmé cette adresse e-mail")

    user = sso_user(
        "google",
        str(profile["sub"]),
        str(profile["email"]).lower(),
        profile.get("name"),
        session,
    )
    return sso_redirect(user)


@router.get("/auth/sso/microsoft")
async def microsoft_login(request: Request):
    if not settings.microsoft_sso_configured:
        raise HTTPException(503, "La connexion Microsoft n’est pas encore configurée")
    callback = f"{settings.api_public_url.rstrip('/')}/api/auth/sso/microsoft/callback"
    return await oauth.microsoft.authorize_redirect(request, callback)


@router.get("/auth/sso/microsoft/callback")
async def microsoft_sso_callback(
    request: Request,
    session: Session = Depends(get_session),
):
    if not settings.microsoft_sso_configured:
        raise HTTPException(503, "La connexion Microsoft n’est pas configurée")
    try:
        token = await oauth.microsoft.authorize_access_token(request)
        profile = token.get("userinfo") or await oauth.microsoft.userinfo(token=token)
    except OAuthError as exc:
        raise HTTPException(400, "La connexion Microsoft a échoué") from exc
    email = str(profile.get("email") or profile.get("preferred_username") or "").lower()
    subject = str(profile.get("sub") or "")
    if not email or not subject:
        raise HTTPException(400, "Microsoft n’a pas fourni une identité exploitable")
    return sso_redirect(
        sso_user("microsoft", subject, email, profile.get("name"), session)
    )


@router.get("/auth/me")
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "agreements_current": has_current_agreements(user.id, session),
    }


def owned_recording(recording_id: str, user: User, session: Session) -> Recording:
    recording = session.get(Recording, recording_id)
    if not recording or recording.owner_id != user.id:
        raise HTTPException(404, "Enregistrement introuvable")
    return recording


def parse_json(value: str | None) -> list:
    return json.loads(value) if value else []


def recording_detail(recording: Recording, session: Session | None = None) -> dict:
    report = (
        session.exec(
            select(StructuredReport).where(StructuredReport.recording_id == recording.id)
        ).first()
        if session
        else None
    )
    result = {
        "id": recording.id,
        "title": recording.title,
        "status": recording.status,
        "created_at": recording.created_at,
        "completed_at": recording.completed_at,
        "error": recording.error,
        "transcript": recording.transcript,
        "segments": parse_json(recording.segments_json),
        "summary": recording.summary,
        "topics": parse_json(recording.topics_json),
        "decisions": parse_json(recording.decisions_json),
        "actions": parse_json(recording.actions_json),
        "consent_version": recording.consent_version,
    }
    if report:
        result["report"] = {
            "model": report.model,
            "language": report.language,
            "detailed_minutes": report.detailed_minutes,
            "speakers": parse_json(report.speakers_json),
            "key_points": parse_json(report.key_points_json),
            "decisions": parse_json(report.decisions_json),
            "actions": parse_json(report.actions_json),
            "open_questions": parse_json(report.open_questions_json),
            "risks": parse_json(report.risks_json),
            "coverage": parse_json(report.coverage_json),
            "podcast_script": parse_json(report.podcast_json),
        }
    return result


@router.post("/recordings", status_code=201)
async def create_recording(
    title: str = Form(..., min_length=1, max_length=120),
    consent: bool = Form(...),
    consent_session_id: str = Form(...),
    audio: UploadFile = File(...),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    if not consent:
        raise HTTPException(400, "Votre consentement est obligatoire")
    meeting = session.get(ConsentSession, consent_session_id)
    if not meeting or meeting.owner_id != user.id:
        raise HTTPException(404, "Réunion de consentement introuvable")
    if meeting.status != ConsentSessionStatus.RECORDING:
        raise HTTPException(409, "La réunion n’est pas autorisée à enregistrer")
    participants = list(
        session.exec(select(ParticipantConsent).where(ParticipantConsent.session_id == meeting.id))
    )
    if not participants or not all(
        item.consented_at and not item.withdrawn_at for item in participants
    ):
        raise HTTPException(409, "Un participant a refusé ou retiré son accord")
    content_type = (audio.content_type or "").split(";")[0].lower()
    extension = ALLOWED_AUDIO.get(content_type)
    if not extension:
        raise HTTPException(415, "Format audio non accepté")
    data = await audio.read(settings.max_audio_mb * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(400, "Le fichier audio est vide")
    if len(data) > settings.max_audio_mb * 1024 * 1024:
        raise HTTPException(413, f"Le fichier dépasse {settings.max_audio_mb} Mo")

    settings.audio_directory.mkdir(parents=True, exist_ok=True)
    recording = Recording(
        owner_id=user.id,
        title=title.strip(),
        original_filename=f"recording{extension}",
        content_type=content_type,
        audio_path="",
        consent_version=CONSENT_VERSION,
    )
    path = settings.audio_directory / f"{recording.id}{extension}"
    path.write_bytes(data)
    recording.audio_path = str(path)
    session.add(recording)
    session.add(SessionRecording(session_id=meeting.id, recording_id=recording.id))
    session.commit()
    session.refresh(recording)
    # Garder la requête active empêche Scaleway d'interrompre le traitement.
    await asyncio.to_thread(process_recording, recording.id)
    session.expire_all()
    return recording_detail(owned_recording(recording.id, user, session), session)


@router.get("/recordings")
def list_recordings(user: User = Depends(current_user), session: Session = Depends(get_session)):
    recordings = session.exec(
        select(Recording).where(Recording.owner_id == user.id).order_by(Recording.created_at.desc())
    ).all()
    return [
        {"id": item.id, "title": item.title, "status": item.status, "created_at": item.created_at}
        for item in recordings
    ]


@router.get("/recordings/{recording_id}")
def get_recording(
    recording_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    return recording_detail(owned_recording(recording_id, user, session), session)


@router.delete("/recordings/{recording_id}", status_code=204)
def delete_recording(
    recording_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    recording = owned_recording(recording_id, user, session)
    link = session.exec(
        select(SessionRecording).where(SessionRecording.recording_id == recording.id)
    ).first()
    if link:
        session.delete(link)
    report = session.exec(
        select(StructuredReport).where(StructuredReport.recording_id == recording.id)
    ).first()
    if report:
        session.delete(report)
    session.flush()
    path = Path(recording.audio_path).resolve()
    if path.is_relative_to(settings.audio_directory) and path.exists():
        path.unlink()
    session.delete(recording)
    session.commit()
