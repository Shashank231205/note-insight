"""The contract with the language model.

Deliberately separate from the API schemas. The model does not assign
condition ids, does not know about owner_uid, and this shape will drift as
prompts evolve — conflating the two would leak model-shaped fields into API
responses.

Fields are permissive about what the model might send (a confidence outside
0-1, a code with stray whitespace) and strict about what leaves this module.
Rejecting the entire response over a formatting quirk would waste a paid call.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import DocumentationStatus, GapSeverity

MAX_CONDITIONS = 25
MAX_GAPS = 25
MAX_SUMMARY_CHARS = 1200
MAX_QUOTE_CHARS = 1000
MAX_NAME_CHARS = 200


class RawCondition(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    condition_name: str = Field(min_length=1, max_length=MAX_NAME_CHARS)
    evidence_quote: str = Field(min_length=1, max_length=MAX_QUOTE_CHARS)
    documentation_status: DocumentationStatus
    icd10_code: str | None = Field(default=None, max_length=16)
    confidence: float

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        """A model that reports 1.2 means "very confident", not "invalid"."""
        return min(max(value, 0.0), 1.0)

    @field_validator("icd10_code")
    @classmethod
    def normalize_icd10_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


class RawGap(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    description: str = Field(min_length=1, max_length=500)
    related_condition_name: str | None = Field(default=None, max_length=MAX_NAME_CHARS)
    severity: GapSeverity = GapSeverity.MEDIUM


class RawAnalysis(BaseModel):
    """The complete structured response, before any of it is trusted."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_CHARS)
    conditions: list[RawCondition] = Field(max_length=MAX_CONDITIONS)
    documentation_gaps: list[RawGap] = Field(max_length=MAX_GAPS)
