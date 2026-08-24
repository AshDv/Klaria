"""Point d’entrée FastAPI."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.consent_routes import router as consent_router
from app.db import init_db
from app.legal_routes import router as legal_router
from app.remote_monitor import (
    bind_monitor_loop,
    resume_remote_monitors,
    stop_remote_monitors,
)
from app.remote_routes import router as remote_router
from app.retention import purge_expired_data, retention_loop
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.audio_directory.mkdir(parents=True, exist_ok=True)
    init_db()
    purge_expired_data()
    retention_task = asyncio.create_task(retention_loop())
    bind_monitor_loop(asyncio.get_running_loop())
    resume_remote_monitors()
    yield
    retention_task.cancel()
    await asyncio.gather(retention_task, return_exceptions=True)
    await stop_remote_monitors()


app = FastAPI(title="Scribe API", version="1.0.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; img-src 'self' data: blob:; "
            "media-src 'self' blob:; connect-src 'self' wss:; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), microphone=(self), payment=(), usb=()"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)
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
app.include_router(remote_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mistral_configured": bool(settings.mistral_api_key),
        "google_sso_configured": settings.google_sso_configured,
        "email_configured": settings.smtp_configured,
        "legal_configured": settings.legal_configured,
        "summary_model": settings.summary_model,
        "meeting_bot_configured": settings.vexa_configured,
    }


static_dir = Path(__file__).resolve().parents[1] / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = (static_dir / path).resolve()
        if candidate.is_relative_to(static_dir) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
