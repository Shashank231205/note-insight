from datetime import datetime

from pydantic import BaseModel

from src.api.schemas.common import RequestBase
from src.models.analysis import Analysis, AnalysisOutput, VerificationReport
from src.models.enums import (
    AnalysisStatus,
    DocumentationStatus,
    GapSeverity,
    ProviderName,
    QuoteVerificationStatus,
)


class RunAnalysisRequest(RequestBase):
    force: bool = False


class ConditionResponse(BaseModel):
    condition_id: str
    name: str
    evidence_quote: str
    documentation_status: DocumentationStatus
    icd10_code: str | None
    confidence: float


class DocumentationGapResponse(BaseModel):
    gap_id: str
    description: str
    related_condition_id: str | None
    severity: GapSeverity


class AnalysisOutputResponse(BaseModel):
    summary: str
    conditions: list[ConditionResponse]
    documentation_gaps: list[DocumentationGapResponse]

    @classmethod
    def from_domain(cls, output: AnalysisOutput) -> "AnalysisOutputResponse":
        return cls(
            summary=output.summary,
            conditions=[
                ConditionResponse(
                    condition_id=condition.condition_id,
                    name=condition.name,
                    evidence_quote=condition.evidence_quote,
                    documentation_status=condition.documentation_status,
                    icd10_code=condition.icd10_code,
                    confidence=condition.confidence,
                )
                for condition in output.conditions
            ],
            documentation_gaps=[
                DocumentationGapResponse(
                    gap_id=gap.gap_id,
                    description=gap.description,
                    related_condition_id=gap.related_condition_id,
                    severity=gap.severity,
                )
                for gap in output.documentation_gaps
            ],
        )


class QuoteVerificationResponse(BaseModel):
    condition_id: str
    status: QuoteVerificationStatus
    match_score: float
    match_offset: int | None
    match_length: int | None


class VerificationReportResponse(BaseModel):
    """Shipped to the UI so a clinician can see which quotes we could not find.

    The offsets are what let the frontend highlight evidence inline in the
    original note.
    """

    checked_at: datetime
    quote_results: list[QuoteVerificationResponse]
    verified_count: int
    unverified_count: int

    @classmethod
    def from_domain(cls, report: VerificationReport) -> "VerificationReportResponse":
        return cls(
            checked_at=report.checked_at,
            quote_results=[
                QuoteVerificationResponse(
                    condition_id=result.condition_id,
                    status=result.status,
                    match_score=result.match_score,
                    match_offset=result.match_offset,
                    match_length=result.match_length,
                )
                for result in report.quote_results
            ],
            verified_count=report.verified_count,
            unverified_count=report.unverified_count,
        )


class AnalysisFailureResponse(BaseModel):
    code: str
    message: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    note_id: str
    status: AnalysisStatus
    provider: ProviderName
    model_id: str
    prompt_version: str
    output: AnalysisOutputResponse | None
    verification: VerificationReportResponse | None
    failure: AnalysisFailureResponse | None
    latency_ms: int
    cache_hit: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, analysis: Analysis) -> "AnalysisResponse":
        return cls(
            analysis_id=analysis.analysis_id,
            note_id=analysis.note_id,
            status=analysis.status,
            provider=analysis.provider,
            model_id=analysis.model_id,
            prompt_version=analysis.prompt_version,
            output=(
                AnalysisOutputResponse.from_domain(analysis.output)
                if analysis.output is not None
                else None
            ),
            verification=(
                VerificationReportResponse.from_domain(analysis.verification)
                if analysis.verification is not None
                else None
            ),
            # The raw model excerpt stays in the database for debugging and is
            # deliberately not returned: it is unvalidated model text.
            failure=(
                AnalysisFailureResponse(
                    code=analysis.failure.code,
                    message=analysis.failure.message,
                )
                if analysis.failure is not None
                else None
            ),
            latency_ms=analysis.latency_ms,
            cache_hit=analysis.cache_hit,
            created_at=analysis.created_at,
        )
