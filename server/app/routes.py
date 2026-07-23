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
