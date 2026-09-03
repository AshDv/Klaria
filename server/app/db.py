"""Connexion base de données avec fallback POC."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _connect_args(url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


def _engine(url: str):
    return create_engine(url, echo=False, connect_args=_connect_args(url))


def _available_engine():
    if settings.database_url.startswith("sqlite"):
        return _engine(settings.database_url)
    try:
        primary = _engine(settings.database_url)
        with primary.connect():
            return primary
    except (ImportError, ModuleNotFoundError, SQLAlchemyError):
        if not settings.allow_database_fallback:
            raise
        return _engine(settings.database_fallback_url)


engine = _available_engine()


def _column_type(sqlite_type: str, postgres_type: str) -> str:
    return sqlite_type if engine.dialect.name == "sqlite" else postgres_type


def _add_missing_columns(table: str, migrations: dict[str, str]) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns(table)}
    with engine.begin() as connection:
        for name, column_type in migrations.items():
            if name not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"
                )


def init_db() -> None:
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    _add_missing_columns("structuredreport", {"podcast_json": "TEXT NOT NULL DEFAULT '[]'"})
    _add_missing_columns(
        "remotemeeting",
        {
            "welcome_posted_at": _column_type("DATETIME", "TIMESTAMP"),
            "recap_posted_at": _column_type("DATETIME", "TIMESTAMP"),
            "chat_error": "TEXT",
            "media_recording_enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
            "media_retention_days": "INTEGER NOT NULL DEFAULT 0",
            "provider_recording_id": "BIGINT",
            "provider_media_id": "INTEGER",
            "media_type": "TEXT",
            "media_format": "TEXT",
            "media_expires_at": _column_type("DATETIME", "TIMESTAMP"),
        },
    )
    _add_missing_columns(
        "consentsession",
        {
            "media_recording_enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
            "media_retention_days": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _add_missing_columns(
        "participantconsent",
        {"erasure_requested_at": _column_type("DATETIME", "TIMESTAMP")},
    )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
