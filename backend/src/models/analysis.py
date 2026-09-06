from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import (
    AnalysisStatus,
    DocumentationStatus,
    GapSeverity,
    ProviderName,
    QuoteVerificationStatus,
)


class Condition(BaseModel):
    """One condition the model identified.

    `condition_id` is assigned by us, never by the model. Reviews reference it,
    so it has to be stable and trustworthy.
    """

    model_config = ConfigDict(frozen=True)

    condition_id: str
    name: str
    evidence_quote: str
    documentation_status: DocumentationStatus
    icd10_code: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class DocumentationGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    gap_id: str
    description: str
    related_condition_id: str | None
    severity: GapSeverity


class AnalysisOutput(BaseModel):
    """The machine's opinion. The only part of the database the model writes."""

    model_config = ConfigDict(frozen=True)

    summary: str
    conditions: list[Condition]
    documentation_gaps: list[DocumentationGap]


class QuoteVerification(BaseModel):
    """The result of looking for one evidence quote in the source note."""

    model_config = ConfigDict(frozen=True)

    condition_id: str
    status: QuoteVerificationStatus
    match_score: float = Field(ge=0.0, le=1.0)
    match_offset: int | None
    match_length: int | None

    @property
    def is_verified(self) -> bool:
        """Only a quote located as one passage counts as verified.

        ASSEMBLED is deliberately excluded. Its fragments are real, which is
        worth telling the clinician, but no such passage exists in the note and
        counting it as evidence would defeat the point of checking.
        """
        return self.status in {
            QuoteVerificationStatus.EXACT,
            QuoteVerificationStatus.NORMALIZED,
            QuoteVerificationStatus.FUZZY,
        }


class VerificationReport(BaseModel):
    """Our answer to "how do you know the model didn't make this up?"."""

    model_config = ConfigDict(frozen=True)

    checked_at: datetime
    quote_results: list[QuoteVerification]
    verified_count: int
    unverified_count: int


class AnalysisFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    raw_excerpt: str | None


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: int
    completion: int
    total: int


class Analysis(BaseModel):
    """One machine opinion about one note, at one prompt version, from one model.

    Immutable. Re-running the prompt creates a new document; this one is never
    mutated, so the pair becomes the evidence for whether a prompt change was
    an improvement.
    """

    model_config = ConfigDict(frozen=True)

    analysis_id: str
    note_id: str
    owner_uid: str

    # Denormalized from the note so a cache lookup is one query rather than a
    # join we cannot express in Firestore.
    content_hash: str

    status: AnalysisStatus
    provider: ProviderName
    model_id: str
    prompt_version: str

    output: AnalysisOutput | None
    verification: VerificationReport | None
    failure: AnalysisFailure | None

    latency_ms: int
    token_usage: TokenUsage | None

    # Describes this *response*, not the stored record: True when the analysis
    # was served from an earlier identical run instead of a fresh model call.
    # Persisted as False and set on the way out, so latency_ms and token_usage
    # keep describing the call that actually produced the output.
    cache_hit: bool

    created_at: datetime

    @property
    def condition_count(self) -> int:
        return len(self.output.conditions) if self.output is not None else 0
