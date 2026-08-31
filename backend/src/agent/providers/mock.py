"""Deterministic provider used for all development and testing.

The entire pipeline is built and verified against this, so Gemini is connected
at the end to something already proven. It also makes the failure paths
reproducible: a hallucinated quote or a truncated response is a fixture here,
not something we wait for the real model to do.

Behaviour is selected by markers in the note text so a reviewer can trigger any
path by hand from the UI. Absent a marker, it produces a plausible analysis by
quoting real spans from the submitted note.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TypedDict

from src.agent.providers.base import ProviderRequest, ProviderResult
from src.core.errors import ProviderUnavailableError
from src.models.analysis import TokenUsage
from src.models.enums import DocumentationStatus, GapSeverity, ProviderName

MOCK_MODEL_ID = "mock-analyst-v1"

TRIGGER_MALFORMED = "[[mock:malformed]]"
TRIGGER_HALLUCINATE = "[[mock:hallucinate]]"
TRIGGER_UNAVAILABLE = "[[mock:unavailable]]"
TRIGGER_INCOMPLETE = "[[mock:incomplete]]"
TRIGGER_EMPTY = "[[mock:no-conditions]]"

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")

_CONDITION_HINTS: tuple[tuple[str, str, str, DocumentationStatus], ...] = (
    ("diabet", "Diabetes mellitus", "E11.9", DocumentationStatus.AMBIGUOUS),
    ("hypertens", "Essential hypertension", "I10", DocumentationStatus.WELL_DOCUMENTED),
    ("ckd", "Chronic kidney disease", "N18.9", DocumentationStatus.AMBIGUOUS),
    ("kidney", "Chronic kidney disease", "N18.9", DocumentationStatus.AMBIGUOUS),
    ("heart failure", "Heart failure", "I50.9", DocumentationStatus.WELL_DOCUMENTED),
    ("copd", "COPD", "J44.9", DocumentationStatus.MENTIONED_WITHOUT_PLAN),
    ("depress", "Depression", "F32.9", DocumentationStatus.MENTIONED_WITHOUT_PLAN),
    ("obes", "Obesity", "E66.9", DocumentationStatus.AMBIGUOUS),
    ("anemia", "Anemia", "D64.9", DocumentationStatus.MENTIONED_WITHOUT_PLAN),
    ("neuropath", "Neuropathy", "G62.9", DocumentationStatus.AMBIGUOUS),
)


class _MockPayload(TypedDict):
    summary: str
    conditions: list[dict[str, object]]
    documentation_gaps: list[dict[str, object]]


def _sentences(text: str) -> list[str]:
    return [match.group().strip() for match in _SENTENCE.finditer(text) if match.group().strip()]


class MockLLMProvider:
    """Implements LLMProvider without any network call."""

    def __init__(self, latency_seconds: float = 0.0) -> None:
        self._latency_seconds = latency_seconds

    @property
    def name(self) -> str:
        return ProviderName.MOCK.value

    @property
    def model_id(self) -> str:
        return MOCK_MODEL_ID

    async def generate_analysis(self, request: ProviderRequest) -> ProviderResult:
        note = request.note_content

        if TRIGGER_UNAVAILABLE in note:
            raise ProviderUnavailableError

        if self._latency_seconds > 0:
            await asyncio.sleep(self._latency_seconds)

        return ProviderResult(
            raw_text=self._response_for(note),
            model_id=self.model_id,
            latency_ms=int(self._latency_seconds * 1000),
            token_usage=TokenUsage(
                prompt=len(note) // 4,
                completion=180,
                total=len(note) // 4 + 180,
            ),
        )

    def _response_for(self, note: str) -> str:
        if TRIGGER_MALFORMED in note:
            return "Certainly! Here is the analysis you asked for: the patient has {diabetes"

        if TRIGGER_INCOMPLETE in note:
            # Valid JSON, wrong shape: `conditions` entries lack the required
            # documentation_status.
            return json.dumps(
                {
                    "summary": "Routine follow-up.",
                    "conditions": [{"condition_name": "Diabetes", "confidence": 0.8}],
                    "documentation_gaps": [],
                }
            )

        if TRIGGER_EMPTY in note:
            return json.dumps(
                {
                    "summary": "Encounter addressed no codeable chronic conditions.",
                    "conditions": [],
                    "documentation_gaps": [],
                }
            )

        payload = self._plausible_analysis(note)

        if TRIGGER_HALLUCINATE in note:
            payload["conditions"].append(
                {
                    "condition_name": "Atrial fibrillation",
                    "evidence_quote": (
                        "Patient reports intermittent palpitations consistent with "
                        "paroxysmal atrial fibrillation, rate controlled on metoprolol."
                    ),
                    "documentation_status": DocumentationStatus.WELL_DOCUMENTED.value,
                    "icd10_code": "I48.0",
                    "confidence": 0.91,
                }
            )

        # Markdown fencing is a real Gemini behaviour; emitting it here keeps
        # the parser's structural recovery on a tested path.
        return f"```json\n{json.dumps(payload, indent=2)}\n```"

    def _plausible_analysis(self, note: str) -> _MockPayload:
        sentences = _sentences(note)
        lowered = note.lower()

        conditions: list[dict[str, object]] = []
        gaps: list[dict[str, object]] = []
        seen: set[str] = set()

        for hint, name, code, status in _CONDITION_HINTS:
            if hint not in lowered or name in seen:
                continue
            quote = next((s for s in sentences if hint in s.lower()), None)
            if quote is None:
                continue

            seen.add(name)
            conditions.append(
                {
                    "condition_name": name,
                    "evidence_quote": quote,
                    "documentation_status": status.value,
                    "icd10_code": code,
                    "confidence": 0.72 if status is DocumentationStatus.AMBIGUOUS else 0.9,
                }
            )
            if status is not DocumentationStatus.WELL_DOCUMENTED:
                gaps.append(
                    {
                        "description": (
                            f"{name} is documented without a clinically material qualifier; "
                            "add type, severity or control status and an explicit plan."
                        ),
                        "related_condition_name": name,
                        "severity": GapSeverity.HIGH.value,
                    }
                )

        if not conditions and sentences:
            conditions.append(
                {
                    "condition_name": "Unspecified clinical finding",
                    "evidence_quote": sentences[0],
                    "documentation_status": DocumentationStatus.MENTIONED_WITHOUT_PLAN.value,
                    "icd10_code": None,
                    "confidence": 0.35,
                }
            )

        return _MockPayload(
            summary=(
                f"Encounter documenting {len(conditions)} condition(s). "
                "Generated by the mock provider for development."
            ),
            conditions=conditions,
            documentation_gaps=gaps,
        )
