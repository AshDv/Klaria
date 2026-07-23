"""Configuration centralisée de Scribe."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Scribe"
    environment: str = "development"
    secret_key: str = "change-this-secret-before-production"
    database_url: str = "sqlite:///./scribe.db"
    cors_origins: str = "http://localhost:5174"
    frontend_url: str = "http://localhost:5174"
    api_public_url: str = "http://localhost:8000"
    token_minutes: int = 60 * 24
    upload_dir: str = "./data/recordings"
    max_audio_mb: int = 50
    result_retention_days: int = 30
    terms_version: str = "2026-07-22"
    privacy_version: str = "2026-07-22"
    data_controller_name: str = ""
    data_controller_address: str = ""
    privacy_contact_email: str = "privacy@example.com"

    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    voxtral_model: str = "voxtral-mini-latest"
    summary_model: str = "mistral-medium-3-5"

    google_client_id: str | None = None
    google_client_secret: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def audio_directory(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def google_sso_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email)

    @property
    def legal_configured(self) -> bool:
        return bool(
            self.data_controller_name
            and self.data_controller_address
            and self.privacy_contact_email != "privacy@example.com"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
