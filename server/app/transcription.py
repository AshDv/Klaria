"""Client Voxtral : audio vers transcription."""

import re
from pathlib import Path

import httpx

from app.config import settings


class TranscriptionError(RuntimeError):
    pass


def context_bias(values: list[str]) -> str:
    """Formate les expressions selon le mode multipart attendu par Mistral."""
    return ",".join(
        item
        for value in values[:100]
        if (item := re.sub(r"[^\w-]+", "_", value.strip()).strip("_"))
    )


def speech_to_text_audio(
    path: Path,
    content_type: str,
    vocabulary: list[str] | None = None,
) -> dict:
    if not settings.mistral_api_key:
        raise TranscriptionError("MISTRAL_API_KEY manque dans server/.env")
    try:
        with path.open("rb") as audio:
            data = {
                "model": settings.voxtral_model,
                "timestamp_granularities": "segment",
                "diarize": "true",
            }
            if vocabulary:
                data["context_bias"] = context_bias(vocabulary)
            response = httpx.post(
                f"{settings.mistral_base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
                data=data,
                files={"file": (path.name, audio, content_type)},
                timeout=httpx.Timeout(90, connect=10),
            )
    except (OSError, httpx.HTTPError) as exc:
        raise TranscriptionError(f"Transcription indisponible : {exc}") from exc
    if response.status_code >= 400:
        try:
            error = response.json()
            detail = error.get("message") or error.get("detail") or error
        except ValueError:
            detail = response.text
        raise TranscriptionError(
            f"Voxtral a refusé l’audio ({response.status_code}) : {str(detail)[:300]}"
        )
    data = response.json()
    text = str(data.get("text", "")).strip()
    if not text:
        raise TranscriptionError("Aucune parole n’a été détectée")
    segments = []
    for index, segment in enumerate(data.get("segments") or []):
        segments.append(
            {
                "id": index,
                "start": segment.get("start"),
                "end": segment.get("end"),
                "speaker": segment.get("speaker_id") or segment.get("speaker") or "speaker_unknown",
                "text": str(segment.get("text", "")).strip(),
            }
        )
    diarized_text = "\n".join(
        f"[{item['start']}] {item['speaker']}: {item['text']}" for item in segments
    )
    return {"text": text, "diarized_text": diarized_text or text, "segments": segments}
