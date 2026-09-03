"""Chiffrement réversible des jetons OAuth stockés en base."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    secret = settings.token_encryption_key or settings.secret_key
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_token(value: str | None) -> str | None:
    return _fernet().encrypt(value.encode()).decode() if value else None


def decrypt_token(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Le jeton d’agenda ne peut plus être déchiffré") from exc
