"""Point d’entrée FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.consent_routes import router as consent_router
from app.db import init_db
from app.legal_routes import router as legal_router
from app.retention import purge_expired_data
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.audio_directory.mkdir(parents=True, exist_ok=True)
    init_db()
    purge_expired_data()
    yield


app = FastAPI(title="Scribe API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.environment == "production",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(consent_router)
app.include_router(legal_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mistral_configured": bool(settings.mistral_api_key),
        "google_sso_configured": settings.google_sso_configured,
        "email_configured": settings.smtp_configured,
        "legal_configured": settings.legal_configured,
        "summary_model": settings.summary_model,
    }
