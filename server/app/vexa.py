"""Vexa : bot qui rejoint Teams/Meet/Zoom, écoute et transcrit (réel, sans mock).

Si VEXA_API_KEY est absent, les appels lèvent une erreur explicite (aucun
fallback / fausse transcription).
Réf : https://docs.vexa.ai/api/bots — https://docs.vexa.ai/api/transcripts
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import settings


class VexaError(RuntimeError):
    pass


def _require_key() -> str:
    if not settings.vexa_api_key:
        raise VexaError("VEXA_API_KEY manquant dans server/.env — requis (aucun mode démo).")
    return settings.vexa_api_key


def parse_url(url: str) -> tuple[str, str, str | None]:
    """Retourne la plateforme, l'identifiant et le code depuis un lien documenté."""
    u = urlparse(url.strip())
    host = (u.hostname or "").lower()
    qs = parse_qs(u.query)
    if u.scheme != "https":
        raise VexaError("Le lien de réunion doit commencer par https://")
    if host == "meet.google.com":
        code = u.path.strip("/").split("/")[-1]
        if not re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", code):
            raise VexaError("Lien Google Meet invalide (attendu meet.google.com/abc-defg-hij).")
        return "google_meet", code, None
    if host in {"teams.live.com", "teams.microsoft.com", "teams.microsoft.us"}:
        path = unquote(u.path)
        m = re.search(r"/meet/(\d{8,15})", path) or re.search(
            r"/(\d{8,15})(?:/|$)", path
        )
        if not m:
            raise VexaError(
                "Lien Teams non reconnu. Utilisez le lien contenant /meet/<ID>?p=<CODE>."
            )
        return "teams", m.group(1), (qs.get("p") or qs.get("passcode") or [None])[0]
    raise VexaError("Plateforme non reconnue. Klaria accepte Google Meet et Microsoft Teams.")


def _headers() -> dict:
    return {"X-API-Key": _require_key(), "Content-Type": "application/json"}


def _endpoint(path: str) -> str:
    return f"{settings.vexa_api_url.rstrip('/')}{path}"


def websocket_url() -> str:
    base = settings.vexa_api_url.rstrip("/")
    scheme = "wss" if base.startswith("https://") else "ws"
    return re.sub(r"^https?", scheme, base) + "/ws"


def api_key() -> str:
    return _require_key()


def send_bot(
    url: str,
    language: str = "fr",
    recording_enabled: bool = False,
) -> tuple[str, str]:
    """Envoie le bot dans la réunion. Retourne (platform, native_id)."""
    platform, native_id, passcode = parse_url(url)
    payload = {
        "platform": platform,
        "native_meeting_id": native_id,
        "language": language,
        "bot_name": settings.vexa_bot_name,
        "recording_enabled": recording_enabled,
        "transcribe_enabled": True,
        "transcription_tier": "realtime",
        "voice_agent_enabled": True,
    }
    if platform == "teams":
        # Vexa doit conserver la forme exacte du lien Teams. Reconstruire un lien
        # /meet/<id> en /l/meetup-join/<id> redirige le bot vers la connexion Microsoft.
        payload["meeting_url"] = url.strip()
    if passcode:
        payload["passcode"] = passcode
    try:
        r = httpx.post(_endpoint("/bots"), headers=_headers(), json=payload, timeout=30)
    except httpx.HTTPError as exc:
        raise VexaError(f"Vexa est injoignable : {exc}") from exc
    # 409 = un bot est déjà actif/demandé pour cette réunion → on le réutilise.
    if r.status_code == 409:
        return platform, native_id
    if r.status_code >= 400:
        raise VexaError(f"Vexa /bots a échoué ({r.status_code}): {r.text[:300]}")
    return platform, native_id


def get_transcript(platform: str, native_id: str) -> dict:
    """Récupère l'état courant : { status, segments[...] }."""
    try:
        r = httpx.get(
            _endpoint(f"/transcripts/{platform}/{native_id}"),
            headers=_headers(),
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise VexaError(f"Vexa est injoignable : {exc}") from exc
    if r.status_code >= 400:
        raise VexaError(f"Vexa /transcripts a échoué ({r.status_code}): {r.text[:300]}")
    return r.json()


def recording_for_meeting(provider_meeting_id: int) -> dict | None:
    """Retourne le média maître associé à une réunion Vexa terminée."""
    try:
        response = httpx.get(_endpoint("/recordings"), headers=_headers(), timeout=30)
    except httpx.HTTPError as exc:
        raise VexaError(f"Vexa est injoignable : {exc}") from exc
    if response.status_code >= 400:
        raise VexaError(f"Vexa /recordings a échoué ({response.status_code})")
    recordings = response.json().get("recordings") or []
    recording = next(
        (item for item in recordings if item.get("meeting_id") == provider_meeting_id),
        None,
    )
    if not recording:
        return None
    media = recording.get("media_files") or []
    audio = next(
        (
            item
            for item in media
            if str(item.get("type") or "").casefold() == "audio"
            or str(item.get("format") or "").casefold() in {"mp3", "wav", "m4a", "ogg"}
        ),
        None,
    )
    return {"recording": recording, "media": audio} if audio else None


def recording_stream(recording_id: int, media_id: int, byte_range: str | None = None):
    """Ouvre un flux média Vexa sans transmettre la clé au navigateur."""
    client = httpx.Client(timeout=60)
    headers = _headers()
    if byte_range:
        headers["Range"] = byte_range
    request = client.build_request(
        "GET",
        _endpoint(f"/recordings/{recording_id}/media/{media_id}/raw"),
        headers=headers,
    )
    try:
        response = client.send(request, stream=True)
    except httpx.HTTPError as exc:
        client.close()
        raise VexaError(f"Le replay Vexa est injoignable : {exc}") from exc
    if response.status_code >= 400:
        response.close()
        client.close()
        raise VexaError(f"Vexa n'a pas retourné le replay ({response.status_code})")
    return client, response


def stop_bot(platform: str, native_id: str) -> None:
    try:
        response = httpx.delete(
            _endpoint(f"/bots/{platform}/{native_id}"), headers=_headers(), timeout=20
        )
    except httpx.HTTPError as exc:
        raise VexaError(f"Impossible d'arrêter le bot : {exc}") from exc
    if response.status_code >= 400 and response.status_code != 404:
        raise VexaError(f"Vexa n'a pas arrêté le bot ({response.status_code})")


def send_chat(platform: str, native_id: str, text: str) -> None:
    """Publie un message visible dans la conversation de la réunion."""
    try:
        response = httpx.post(
            _endpoint(f"/bots/{platform}/{native_id}/chat"),
            headers=_headers(),
            json={"text": text},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise VexaError(f"Impossible d'écrire dans le chat : {exc}") from exc
    if response.status_code >= 400:
        raise VexaError(f"Vexa n'a pas publié le message ({response.status_code})")


def get_chat(platform: str, native_id: str) -> list[dict]:
    """Lit les messages captés par le bot pendant la réunion."""
    try:
        response = httpx.get(
            _endpoint(f"/bots/{platform}/{native_id}/chat"),
            headers=_headers(),
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise VexaError(f"Impossible de lire le chat : {exc}") from exc
    if response.status_code == 404:
        return []
    if response.status_code >= 400:
        raise VexaError(f"Vexa n'a pas retourné le chat ({response.status_code})")
    data = response.json()
    messages = data.get("messages") if isinstance(data, dict) else data
    return messages if isinstance(messages, list) else []


def delete_meeting(platform: str, native_id: str) -> None:
    try:
        response = httpx.delete(
            _endpoint(f"/meetings/{platform}/{native_id}"),
            headers=_headers(),
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise VexaError(f"Impossible d'effacer les données Vexa : {exc}") from exc
    if response.status_code >= 400 and response.status_code != 404:
        raise VexaError(
            f"Vexa n'a pas effacé la réunion ({response.status_code}): "
            f"{response.text[:200]}"
        )


def _timestamp(value) -> float | None:
    """Convertit un nombre Unix ou une date ISO en secondes Unix."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None


def _plain_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def clean_speaker(value: str | None) -> str:
    """Écarte les libellés techniques produits par les sous-titres."""
    raw = re.sub(r"[*_`#]+", "", str(value or "")).strip()
    plain = _plain_text(raw)
    invalid = (
        not plain
        or plain.startswith(("sous titrage", "sous titre", "caption", "subtitle"))
        or bool(re.fullmatch(r"(?:st|cc|speaker|intervenant|unknown|inconnu)[\s_-]*\d*", plain))
        or bool(re.fullmatch(r"\d+", plain))
    )
    return "Intervenant non identifié" if invalid else raw[:120]


def _relative_time(item: dict, field: str, base: float | None) -> float:
    relative = _timestamp(item.get(field) or item.get(field.removesuffix("_time")))
    absolute = _timestamp(item.get(f"absolute_{field}"))
    # Vexa peut renvoyer par erreur un timestamp Unix dans start_time/end_time.
    if (
        relative is not None
        and 0 <= relative < 86_400
        and not (field == "end_time" and relative == 0 and absolute is not None)
    ):
        return relative
    candidate = absolute if absolute is not None else relative
    return max(0.0, candidate - base) if candidate is not None and base else 0.0


def _same_mutable_segment(left: dict, right: dict) -> bool:
    if left.get("segment_uid") and left["segment_uid"] == right.get("segment_uid"):
        return True
    if left["speaker"] != right["speaker"] or abs(left["start"] - right["start"]) > 2:
        return False
    left_text, right_text = _plain_text(left["text"]), _plain_text(right["text"])
    return bool(left_text and right_text and (left_text in right_text or right_text in left_text))


def normalize_segments(data: dict) -> list[dict]:
    """Stabilise les segments mutables Vexa et retire leurs versions en double."""
    source = data.get("segments") or (data.get("data") or {}).get("segments") or []
    absolute_starts = [
        value
        for item in source
        if (value := _timestamp(item.get("absolute_start_time"))) is not None
    ]
    base = min(absolute_starts) if absolute_starts else None
    candidates = []
    for item in source:
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if not text:
            continue
        start = _relative_time(item, "start_time", base)
        end = max(start, _relative_time(item, "end_time", base))
        candidates.append(
            {
                "id": 0,
                "segment_uid": item.get("segment_id") or item.get("utterance_id"),
                "start": round(start, 3),
                "end": round(end, 3),
                "speaker": clean_speaker(item.get("speaker")),
                "text": text,
                "completed": bool(item.get("completed", True)),
                "language": item.get("language"),
                "speaker_mapping_status": item.get("speaker_mapping_status"),
                "absolute_start_time": item.get("absolute_start_time"),
                "absolute_end_time": item.get("absolute_end_time"),
            }
        )

    stable = []
    for candidate in sorted(candidates, key=lambda item: (item["start"], item["end"])):
        duplicate = next(
            (item for item in reversed(stable[-6:]) if _same_mutable_segment(item, candidate)),
            None,
        )
        if duplicate:
            # Une transcription temps réel grandit mot après mot : on garde la version
            # la plus complète, puis l'état final et la borne de fin la plus récente.
            if len(_plain_text(candidate["text"])) >= len(_plain_text(duplicate["text"])):
                duplicate.update(candidate)
            duplicate["completed"] = duplicate["completed"] or candidate["completed"]
            duplicate["end"] = max(duplicate["end"], candidate["end"])
            continue
        stable.append(candidate)
    return [{**item, "id": index} for index, item in enumerate(stable)]


def normalize_timeline(segments: list[dict]) -> list[dict]:
    """Répare les temps Vexa déjà stockés sans changer les IDs du rapport."""
    absolute_starts = [
        value
        for item in segments
        if (value := _timestamp(item.get("absolute_start_time"))) is not None
    ]
    base = min(absolute_starts) if absolute_starts else None
    result = []
    for index, item in enumerate(segments):
        start = _relative_time(item, "start_time", base)
        end = _relative_time(item, "end_time", base)
        if end <= start:
            words = len(str(item.get("text") or "").split())
            end = start + max(1.5, words / 2.4)
        result.append(
            {**item, "id": item.get("id", index), "start": round(start, 3), "end": round(end, 3)}
        )
    return result


def transcript_text(data: dict) -> str:
    lines = [f"{item['speaker']}: {item['text']}" for item in normalize_segments(data)]
    return "\n".join(lines)
