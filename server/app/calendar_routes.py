"""Connexion des agendas et contrôle de l’automatisation."""

from contextlib import suppress
from datetime import timedelta
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import current_user
from app.calendar_service import (
    CalendarError,
    _ensure_consent,
    calendar_event_detail,
    run_automation,
    sync_connection,
)
from app.config import settings
from app.db import get_session
from app.models import CalendarConnection, CalendarEvent, CalendarProvider, User, utc_now
from app.token_crypto import encrypt_token

router = APIRouter(prefix="/api")


class AutomationInput(BaseModel):
    enabled: bool
    media_recording_enabled: bool = False
    media_retention_days: int = Field(default=7, ge=1, le=30)


def _state(user_id: str, provider: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "provider": provider,
            "purpose": "calendar_connection",
            "exp": utc_now() + timedelta(minutes=10),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def _state_user(value: str, provider: str) -> str:
    try:
        data = jwt.decode(value, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(400, "Cette connexion d’agenda a expiré") from exc
    if data.get("purpose") != "calendar_connection" or data.get("provider") != provider:
        raise HTTPException(400, "État OAuth invalide")
    return str(data["sub"])


def _callback(provider: str) -> str:
    return f"{settings.api_public_url.rstrip('/')}/api/calendars/{provider}/callback"


def _oauth_error(message: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/?calendar_error={quote(message)}")


def _token_request(url: str, data: dict) -> dict:
    try:
        response = httpx.post(url, data=data, timeout=20)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "La connexion à l’agenda a échoué") from exc


def _save_connection(
    user_id: str,
    provider: CalendarProvider,
    email: str,
    token: dict,
    db: Session,
) -> CalendarConnection:
    connection = db.exec(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == provider,
            CalendarConnection.account_email == email.lower(),
        )
    ).first()
    if not connection:
        connection = CalendarConnection(
            user_id=user_id,
            provider=provider,
            account_email=email.lower(),
            access_token="",
        )
    connection.access_token = encrypt_token(token["access_token"]) or ""
    if token.get("refresh_token"):
        connection.refresh_token = encrypt_token(token["refresh_token"])
    connection.token_expires_at = utc_now() + timedelta(seconds=int(token.get("expires_in", 3600)))
    connection.scopes = token.get("scope", connection.scopes)
    connection.active = True
    connection.updated_at = utc_now()
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.get("/calendars")
def calendar_status(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    connections = db.exec(select(CalendarConnection).where(CalendarConnection.user_id == user.id))
    return {
        "google_available": settings.google_sso_configured,
        "microsoft_available": settings.microsoft_calendar_configured,
        "connections": [
            {
                "id": item.id,
                "provider": item.provider,
                "account_email": item.account_email,
                "active": item.active,
                "last_synced_at": item.last_synced_at,
            }
            for item in connections
        ],
    }


@router.get("/calendars/google/connect")
def connect_google(user: User = Depends(current_user)):
    if not settings.google_sso_configured:
        raise HTTPException(503, "Google OAuth n’est pas configuré")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _callback("google"),
        "response_type": "code",
        "scope": settings.google_calendar_scopes,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": _state(user.id, "google"),
    }
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"}


@router.get("/calendars/google/callback")
def google_callback(request: Request, db: Session = Depends(get_session)):
    if error := request.query_params.get("error"):
        return _oauth_error(f"Google : {error}")
    user_id = _state_user(request.query_params.get("state", ""), "google")
    token = _token_request(
        "https://oauth2.googleapis.com/token",
        {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": request.query_params.get("code", ""),
            "redirect_uri": _callback("google"),
            "grant_type": "authorization_code",
        },
    )
    profile = httpx.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=20,
    ).json()
    connection = _save_connection(
        user_id, CalendarProvider.GOOGLE, profile.get("email", ""), token, db
    )
    with suppress(CalendarError):
        sync_connection(connection, db)
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/?calendar_connected=google")


@router.get("/calendars/microsoft/connect")
def connect_microsoft(user: User = Depends(current_user)):
    if not settings.microsoft_calendar_configured:
        raise HTTPException(503, "Microsoft Entra n’est pas encore configuré")
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": _callback("microsoft"),
        "response_type": "code",
        "response_mode": "query",
        "scope": settings.microsoft_calendar_scopes,
        "state": _state(user.id, "microsoft"),
    }
    tenant = settings.microsoft_tenant
    return {
        "url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{urlencode(params)}"
    }


@router.get("/calendars/microsoft/callback")
def microsoft_callback(request: Request, db: Session = Depends(get_session)):
    if error := request.query_params.get("error"):
        return _oauth_error(f"Microsoft : {error}")
    user_id = _state_user(request.query_params.get("state", ""), "microsoft")
    tenant = settings.microsoft_tenant
    token = _token_request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "code": request.query_params.get("code", ""),
            "redirect_uri": _callback("microsoft"),
            "grant_type": "authorization_code",
            "scope": settings.microsoft_calendar_scopes,
        },
    )
    profile = httpx.get(
        "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName",
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=20,
    ).json()
    email = profile.get("mail") or profile.get("userPrincipalName") or ""
    connection = _save_connection(user_id, CalendarProvider.MICROSOFT, email, token, db)
    with suppress(CalendarError):
        sync_connection(connection, db)
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/?calendar_connected=microsoft")


@router.post("/calendars/sync")
def sync_calendars(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    total = 0
    errors = []
    connections = db.exec(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user.id,
            CalendarConnection.active == True,  # noqa: E712
        )
    )
    for connection in connections:
        try:
            total += sync_connection(connection, db)
        except CalendarError as exc:
            errors.append({"provider": connection.provider, "message": str(exc)})
    return {"synced": total, "errors": errors}


@router.get("/calendar-events")
def list_calendar_events(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    events = db.exec(
        select(CalendarEvent)
        .where(CalendarEvent.owner_id == user.id)
        .order_by(CalendarEvent.starts_at)
    )
    return [calendar_event_detail(item) for item in events]


@router.put("/calendar-events/{event_id}/automation")
def configure_event(
    event_id: str,
    payload: AutomationInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    event = db.get(CalendarEvent, event_id)
    if not event or event.owner_id != user.id:
        raise HTTPException(404, "Réunion calendrier introuvable")
    if payload.enabled and not event.attendees_json.strip("[]"):
        raise HTTPException(409, "Cette invitation ne contient aucun participant")
    event.auto_join = payload.enabled
    db.add(event)
    db.commit()
    if payload.enabled:
        _ensure_consent(
            event,
            db,
            payload.media_recording_enabled,
            payload.media_retention_days,
        )
    return calendar_event_detail(event)


@router.delete("/calendars/{connection_id}", status_code=204)
def disconnect_calendar(
    connection_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    connection = db.get(CalendarConnection, connection_id)
    if not connection or connection.user_id != user.id:
        raise HTTPException(404, "Agenda introuvable")
    connection.active = False
    connection.access_token = ""
    connection.refresh_token = None
    connection.updated_at = utc_now()
    db.add(connection)
    db.commit()


@router.post("/automation/tick")
def automation_tick(
    x_automation_key: str | None = Header(default=None),
    db: Session = Depends(get_session),
):
    if not settings.automation_key or x_automation_key != settings.automation_key:
        raise HTTPException(401, "Clé d’automatisation invalide")
    return run_automation(db)
