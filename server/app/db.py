"""Base de données SQLite (SQLModel)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_args)


def init_db() -> None:
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        columns = {item["name"] for item in inspect(engine).get_columns("structuredreport")}
        if "podcast_json" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE structuredreport ADD COLUMN "
                    "podcast_json TEXT NOT NULL DEFAULT '[]'"
                )
        remote_columns = {
            item["name"] for item in inspect(engine).get_columns("remotemeeting")
        }
        migrations = {
            "welcome_posted_at": "DATETIME",
            "recap_posted_at": "DATETIME",
            "chat_error": "TEXT",
            "media_recording_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "media_retention_days": "INTEGER NOT NULL DEFAULT 0",
            "provider_recording_id": "BIGINT",
            "provider_media_id": "INTEGER",
            "media_type": "TEXT",
            "media_format": "TEXT",
            "media_expires_at": "DATETIME",
        }
        with engine.begin() as connection:
            for name, column_type in migrations.items():
                if name not in remote_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE remotemeeting ADD COLUMN {name} {column_type}"
                    )
        consent_columns = {
            item["name"] for item in inspect(engine).get_columns("consentsession")
        }
        consent_migrations = {
            "media_recording_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "media_retention_days": "INTEGER NOT NULL DEFAULT 0",
        }
        with engine.begin() as connection:
            for name, column_type in consent_migrations.items():
                if name not in consent_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE consentsession ADD COLUMN {name} {column_type}"
                    )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
