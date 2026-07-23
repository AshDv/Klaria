"""Compte rendu fidèle et traçable avec Mistral Medium 3.5."""

import json
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings


class SummaryError(RuntimeError):
    pass


class Speaker(BaseModel):
    label: str
    participant_name: str | None = None
    confidence: Literal["explicit", "unknown"]


class KeyPoint(BaseModel):
    topic: str
    detail: str
    speakers: list[str]
    segment_ids: list[int]


class Decision(BaseModel):
    decision: str
    decided_by: list[str]
    rationale: str | None = None
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


class MeetingSummary(BaseModel):
    language: str
    executive_summary: str = Field(min_length=1, max_length=4000)
    detailed_minutes: str = Field(min_length=1, max_length=12000)
    speakers: list[Speaker]
    key_points: list[KeyPoint]
    decisions: list[Decision]
    actions: list[ActionItem]
    open_questions: list[OpenQuestion]
    risks: list[Risk]
    coverage: list[Coverage]


SYSTEM_PROMPT = """# Role
You are a meticulous meeting secretary. Produce a factual, auditable report.

# Rules
- Use only the supplied diarized segments. Never invent, complete or guess facts.
- Preserve dates, numbers, objections, commitments and uncertainty.
- Link every extracted item to its source segment_ids.
- Include every segment exactly once in coverage, even filler or inaudible content.
- Summarize useful speech; do not repeat filler merely to claim full coverage.
- Assign an action only when the task is explicit. Set owner or due_date to null
  when it is not explicit.
- Map a speaker label to a participant name only after explicit self-identification
  or an unambiguous statement in the transcript. Otherwise keep it unknown.
- Do not expose participant e-mail addresses or infer sensitive attributes.
- Write in the dominant language of the meeting.
- Output only data conforming to the provided JSON schema.
"""


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
                "top_p": 1,
                "reasoning_effort": "high",
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
            timeout=240,
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
    covered = [item.segment_id for item in result.coverage]
    if set(covered) != expected or len(covered) != len(expected):
        raise SummaryError("La couverture des segments est incomplète")
    return result
