"""API Scribe."""

"""API du MVP : comptes, SSO, dictaphone et résultats."""

import json

from pathlib import Path

from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth, OAuthError

from fastapi import (
    APIRouter,
    BackgroundTasks,
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

    subject = str(profile["sub"])
    identity = session.exec(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "google", ExternalIdentity.subject == subject
        )
    ).first()
    user = session.get(User, identity.user_id) if identity else None
    if not user:
        email = str(profile["email"]).lower()
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(
                email=email,
                full_name=profile.get("name") or email.split("@")[0],
                hashed_password="!google-sso",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        session.add(ExternalIdentity(user_id=user.id, provider="google", subject=subject))
        session.commit()

    access_token = quote(create_access_token(user.id), safe="")
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/#access_token={access_token}")

@router.get("/auth/me")
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "agreements_current": has_current_agreements(user.id, session),
    }
