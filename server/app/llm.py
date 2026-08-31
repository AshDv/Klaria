"""Compte rendu fidèle et traçable avec Mistral Medium 3.5."""

import json
import re
import unicodedata
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.meeting_skills import build_system_prompt


class SummaryError(RuntimeError):
    pass


class Speaker(BaseModel):
    label: str
    participant_name: str | None = None
    confidence: Literal["platform", "explicit", "unknown"]


class KeyPoint(BaseModel):
    topic: str
    detail: str
    speakers: list[str]
    segment_ids: list[int]


class Decision(BaseModel):
    decision: str
    status: Literal["confirmed", "proposed", "deferred"] = "confirmed"
    decided_by: list[str]
    rationale: str | None = None
    segment_ids: list[int]


class Mention(BaseModel):
    mentioned_person: str
    speaker: str
    context: str
    segment_ids: list[int]


class ActionItem(BaseModel):
    task: str = Field(min_length=1, max_length=300)
    owner: str | None = None
    due_date: str | None = None
    priority: Literal["low", "medium", "high"] | None = None
    segment_ids: list[int]


class OpenQuestion(BaseModel):
    question: str
    owner: str | None = None
    segment_ids: list[int]


class Risk(BaseModel):
    risk: str
    mitigation: str | None = None
    owner: str | None = None
    segment_ids: list[int]


class Coverage(BaseModel):
    segment_id: int
    classification: Literal[
        "information",
        "decision",
        "action",
        "question",
        "social",
        "filler",
        "inaudible",
    ]
    used_in: list[str]
    exclusion_reason: str | None = None


class PodcastTurn(BaseModel):
    host: Literal["host_a", "host_b"]
    text: str = Field(min_length=1, max_length=700)
    segment_ids: list[int] = Field(min_length=1)


class PodcastOverview(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(min_length=1, max_length=300)
    format: Literal["deep_dive", "brief", "critique", "debate"]
    estimated_minutes: int = Field(ge=1, le=15)
    turns: list[PodcastTurn] = Field(min_length=6, max_length=30)


class MeetingSummary(BaseModel):
    language: str
    executive_summary: str = Field(min_length=1, max_length=4000)
    detailed_minutes: str = Field(min_length=1, max_length=12000)
    speakers: list[Speaker]
    key_points: list[KeyPoint]
    mentions: list[Mention]
    decisions: list[Decision]
    actions: list[ActionItem]
    open_questions: list[OpenQuestion]
    risks: list[Risk]
    podcast_script: list[PodcastTurn] = Field(min_length=4, max_length=14)
    coverage: list[Coverage]


SYSTEM_PROMPT = build_system_prompt()


def _evidence_ids(result: MeetingSummary) -> list[int]:
    sections = (
        result.key_points,
        result.mentions,
        result.decisions,
        result.actions,
        result.open_questions,
        result.risks,
    )
    return [
        segment_id
        for section in sections
        for item in section
        for segment_id in item.segment_ids
    ]


def _repair_coverage(result: MeetingSummary, expected: set[int]) -> None:
    """Rend la table de traçabilité totale sans modifier les faits du rapport."""
    section_ids = {
        "key_points": {item_id for item in result.key_points for item_id in item.segment_ids},
        "mentions": {item_id for item in result.mentions for item_id in item.segment_ids},
        "decisions": {item_id for item in result.decisions for item_id in item.segment_ids},
        "actions": {item_id for item in result.actions for item_id in item.segment_ids},
        "open_questions": {
            item_id for item in result.open_questions for item_id in item.segment_ids
        },
        "risks": {item_id for item in result.risks for item_id in item.segment_ids},
    }
    existing = {
        item.segment_id: item for item in result.coverage if item.segment_id in expected
    }
    repaired = []
    for segment_id in sorted(expected):
        used_in = [name for name, item_ids in section_ids.items() if segment_id in item_ids]
        if segment_id in existing:
            item = existing[segment_id]
            item.used_in = sorted(set(item.used_in) | set(used_in))
            repaired.append(item)
            continue
        classification = next(
            (
                name
                for name, section in (
                    ("decision", "decisions"),
                    ("action", "actions"),
                    ("question", "open_questions"),
                )
                if segment_id in section_ids[section]
            ),
            "information",
        )
        repaired.append(
            Coverage(
                segment_id=segment_id,
                classification=classification,
                used_in=used_in,
                exclusion_reason=None if used_in else "Passage conservé dans le transcript.",
            )
        )
    result.coverage = repaired


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _protect_speaker_identity(result: MeetingSummary, segments: list[dict]) -> None:
    """Empêche un nom invité de devenir une identité sans preuve audio/plateforme."""
    generic = re.compile(
        r"^(speaker|intervenant|unknown|inconnu|sous titrage|sous titre|caption|subtitle)"
        r"(\s+\w+)?$",
        re.I,
    )
    labels = {_plain(item["speaker"]) for item in segments}
    for speaker in result.speakers:
        label = _plain(speaker.label)
        if generic.fullmatch(label):
            speaker.participant_name = None
            speaker.confidence = "unknown"
        elif speaker.participant_name and label == _plain(speaker.participant_name):
            speaker.confidence = "platform"
        elif label not in labels:
            speaker.participant_name = None
            speaker.confidence = "unknown"


def _clean_report_text(value: str) -> str:
    """Transforme le Markdown accidentel du modèle en texte lisible et sûr."""
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", value)
    value = re.sub(
        r"\*\*(.*?)\*\*|__(.*?)__",
        lambda match: match.group(1) or match.group(2),
        value,
    )
    value = re.sub(r"(?m)^\s*[-*]\s+", "• ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def generate_summary(
    transcript: str,
    segments: list[dict],
    participant_names: list[str],
) -> MeetingSummary:
    if not settings.mistral_api_key:
        raise SummaryError("MISTRAL_API_KEY manque dans server/.env")

    payload = {
        "participants": participant_names,
        "full_transcript": transcript,
        "diarized_segments": segments,
    }
    schema = MeetingSummary.model_json_schema()
    try:
        response = httpx.post(
            f"{settings.mistral_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
            json={
                "model": settings.summary_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                "temperature": 0,
                "random_seed": 7,
                "top_p": 1,
                "reasoning_effort": "none",
                "safe_prompt": True,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "meeting_report",
                        "schema": schema,
                        "strict": True,
                    },
                },
            },
            timeout=httpx.Timeout(120, connect=10),
        )
    except httpx.HTTPError as exc:
        raise SummaryError(f"Résumé indisponible : {exc}") from exc
    if response.status_code >= 400:
        raise SummaryError(f"Mistral a refusé la demande ({response.status_code})")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        result = MeetingSummary.model_validate_json(content)
    except (KeyError, TypeError, ValidationError) as exc:
        raise SummaryError("Mistral a renvoyé un compte rendu invalide") from exc

    expected = {item["id"] for item in segments}
    if not set(_evidence_ids(result)).issubset(expected):
        raise SummaryError("Le compte rendu cite un segment inexistant")
    _repair_coverage(result, expected)
    _protect_speaker_identity(result, segments)
    result.executive_summary = _clean_report_text(result.executive_summary)
    result.detailed_minutes = _clean_report_text(result.detailed_minutes)
    for index, turn in enumerate(result.podcast_script):
        expected_host = "host_a" if index % 2 == 0 else "host_b"
        if turn.host != expected_host:
            raise SummaryError("Les voix du brief audio doivent alterner")
        if not set(turn.segment_ids).issubset(expected):
            raise SummaryError("Le brief audio cite un segment inexistant")
    return result


def generate_podcast(
    report: dict,
    segments: list[dict],
    podcast_format: Literal["deep_dive", "brief", "critique", "debate"],
    minutes: int,
    focus: str | None = None,
) -> PodcastOverview:
    """Crée un nouveau brief audio sans sortir des preuves de la réunion."""
    if not settings.mistral_api_key:
        raise SummaryError("MISTRAL_API_KEY manque dans server/.env")
    minutes = max(1, min(minutes, 15))
    prompt = f"""You create a source-grounded French audio overview with two hosts.
Thomas (host_a) is curious and structures the discussion. Camille (host_b) is
analytical and tests the implications. Alternate strictly, start with host_a,
and never add a fact, opinion or recommendation absent from the supplied
meeting. Every turn must cite at least one valid segment_id.

Format: {podcast_format}. Target length: about {minutes} minutes.
Requested focus: {focus or 'the most useful decisions, actions and unresolved points'}.
- deep_dive: connect context, decisions, actions and consequences conversationally.
- brief: deliver only the essentials, without repetition.
- critique: examine explicit strengths, limits and risks without inventing criticism.
- debate: contrast only viewpoints that were actually expressed in the meeting.
Return only JSON matching the schema."""
    payload = {
        "segments": segments,
        "verified_report": {
            key: report.get(key, [])
            for key in (
                "executive_summary",
                "key_points",
                "decisions",
                "actions",
                "open_questions",
                "risks",
            )
        },
    }
    try:
        response = httpx.post(
            f"{settings.mistral_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
            json={
                "model": settings.summary_model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "random_seed": 11,
                "safe_prompt": True,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "podcast_overview",
                        "schema": PodcastOverview.model_json_schema(),
                        "strict": True,
                    },
                },
            },
            timeout=httpx.Timeout(120, connect=10),
        )
    except httpx.HTTPError as exc:
        raise SummaryError(f"Brief audio indisponible : {exc}") from exc
    if response.status_code >= 400:
        raise SummaryError(f"Mistral a refusé le brief audio ({response.status_code})")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        overview = PodcastOverview.model_validate_json(content)
    except (KeyError, TypeError, ValidationError) as exc:
        raise SummaryError("Mistral a renvoyé un brief audio invalide") from exc
    expected = {item["id"] for item in segments}
    if overview.format != podcast_format:
        raise SummaryError("Le format du brief audio ne correspond pas à la demande")
    for index, turn in enumerate(overview.turns):
        host = "host_a" if index % 2 == 0 else "host_b"
        if turn.host != host or not turn.segment_ids or not set(turn.segment_ids) <= expected:
            raise SummaryError("Le brief audio n'est pas correctement relié au transcript")
    return overview
