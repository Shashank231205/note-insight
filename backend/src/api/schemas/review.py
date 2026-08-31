from datetime import datetime

from pydantic import BaseModel, Field

from src.api.schemas.common import RequestBase
from src.models.enums import ConditionOrigin, DocumentationStatus, ReviewAction
from src.models.review import Review

CONDITION_NAME_MAX_LENGTH = 200
QUOTE_MAX_LENGTH = 1000
REASON_MAX_LENGTH = 500
GAP_DESCRIPTION_MAX_LENGTH = 500
SUMMARY_MAX_LENGTH = 1200
REVIEWER_NOTE_MAX_LENGTH = 2000
MAX_REVIEWED_ITEMS = 50


class ReviewedConditionInput(RequestBase):
    """One condition as the clinician left it.

    The AI's original values are not sent back and are not stored here. The
    diff is computed against the analysis on condition_id, so there is exactly
    one record of what the model said.
    """

    condition_id: str = Field(min_length=1)
    origin: ConditionOrigin
    action: ReviewAction

    name: str = Field(min_length=1, max_length=CONDITION_NAME_MAX_LENGTH)
    evidence_quote: str = Field(max_length=QUOTE_MAX_LENGTH)
    documentation_status: DocumentationStatus
    icd10_code: str | None = Field(default=None, max_length=16)
    rejection_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)


class ReviewedGapInput(RequestBase):
    gap_id: str = Field(min_length=1)
    origin: ConditionOrigin
    action: ReviewAction
    description: str = Field(min_length=1, max_length=GAP_DESCRIPTION_MAX_LENGTH)


class SubmitReviewRequest(RequestBase):
    reviewed_conditions: list[ReviewedConditionInput] = Field(max_length=MAX_REVIEWED_ITEMS)
    reviewed_gaps: list[ReviewedGapInput] = Field(
        default_factory=list, max_length=MAX_REVIEWED_ITEMS
    )
    summary_override: str | None = Field(default=None, max_length=SUMMARY_MAX_LENGTH)
    reviewer_note: str | None = Field(default=None, max_length=REVIEWER_NOTE_MAX_LENGTH)


class ReviewedConditionResponse(BaseModel):
    condition_id: str
    origin: ConditionOrigin
    action: ReviewAction
    name: str
    evidence_quote: str
    documentation_status: DocumentationStatus
    icd10_code: str | None
    rejection_reason: str | None


class ReviewedGapResponse(BaseModel):
    gap_id: str
    origin: ConditionOrigin
    action: ReviewAction
    description: str


class ReviewResponse(BaseModel):
    review_id: str
    analysis_id: str
    note_id: str
    version: int
    reviewed_conditions: list[ReviewedConditionResponse]
    reviewed_gaps: list[ReviewedGapResponse]
    summary_override: str | None
    reviewer_note: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, review: Review) -> "ReviewResponse":
        return cls(
            review_id=review.review_id,
            analysis_id=review.analysis_id,
            note_id=review.note_id,
            version=review.version,
            reviewed_conditions=[
                ReviewedConditionResponse(
                    condition_id=condition.condition_id,
                    origin=condition.origin,
                    action=condition.action,
                    name=condition.name,
                    evidence_quote=condition.evidence_quote,
                    documentation_status=condition.documentation_status,
                    icd10_code=condition.icd10_code,
                    rejection_reason=condition.rejection_reason,
                )
                for condition in review.reviewed_conditions
            ],
            reviewed_gaps=[
                ReviewedGapResponse(
                    gap_id=gap.gap_id,
                    origin=gap.origin,
                    action=gap.action,
                    description=gap.description,
                )
                for gap in review.reviewed_gaps
            ],
            summary_override=review.summary_override,
            reviewer_note=review.reviewer_note,
            created_at=review.created_at,
        )
