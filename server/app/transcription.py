"""Client Voxtral : audio vers texte."""

from pathlib import Path

import httpx

from app.config import settings


class TranscriptionError(RuntimeError):
    pass


def transcribe_audio(path: Path, content_type: str, vocabulary: list[str] | None = None) -> dict:
    if not settings.mistral_api_key:
        raise TranscriptionError("MISTRAL_API_KEY manque dans server/.env")
    try:
        with path.open("rb") as audio:
            response = httpx.post(
                f"{settings.mistral_base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
                data={"model": settings.voxtral_model},
                files={"file": (path.name, audio, content_type)},
                timeout=300,
            )
    except (OSError, httpx.HTTPError) as exc:
        raise TranscriptionError(f"Transcription indisponible : {exc}") from exc
    if response.status_code >= 400:
        raise TranscriptionError(f"Voxtral a refusé l’audio ({response.status_code})")
    text = str(response.json().get("text", "")).strip()
    if not text:
        raise TranscriptionError("Aucune parole n’a été détectée")
    return {"text": text, "diarized_text": text, "segments": []}
