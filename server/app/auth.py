"""Mots de passe, jetons de session et utilisateur courant."""

from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("!"):
        return False
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed_password.encode())
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.token_minutes)
    return jwt.encode({"sub": user_id, "exp": expires_at}, settings.secret_key, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2), session: Session = Depends(get_session)) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Connexion requise",
        {"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        raise unauthorized from None
    user = session.get(User, user_id) if user_id else None
    if not user:
        raise unauthorized
    return user
