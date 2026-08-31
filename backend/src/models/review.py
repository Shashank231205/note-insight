from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.enums import ConditionOrigin, DocumentationStatus, ReviewAction


class ReviewedCondition(BaseModel):
    """The human-authoritative version of one condition.

    The AI's values are deliberately not copied here. To answer "what changed",
    read the analysis and the review side by side and diff on condition_id.
    Copying would create a second source of truth, and the first bug would be
    a stale copy.
    """

    model_config = ConfigDict(frozen=True)

    condition_id: str
    origin: ConditionOrigin
    action: ReviewAction

    name: str
    evidence_quote: str
    documentation_status: DocumentationStatus
    icd10_code: str | None

    rejection_reason: str | None


class ReviewedGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    gap_id: str
    origin: ConditionOrigin
    action: ReviewAction
    description: str


class Review(BaseModel):
    """One clinician's corrected version of one analysis.

    Versioned rather than mutated: submitting again creates version n+1 and the
    earlier version survives, which is what makes the correction history an
    audit trail rather than a snapshot.
    """

    model_config = ConfigDict(frozen=True)

    review_id: str
    analysis_id: str
    note_id: str
    owner_uid: str

    version: int

    reviewed_conditions: list[ReviewedCondition]
    reviewed_gaps: list[ReviewedGap]
    summary_override: str | None
    reviewer_note: str | None

    created_at: datetime

    @property
    def accepted_condition_count(self) -> int:
        return sum(
            1
            for condition in self.reviewed_conditions
            if condition.action is not ReviewAction.REJECTED
        )
