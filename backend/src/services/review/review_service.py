"""Human review of an analysis.

The invariants enforced here depend on the analysis being reviewed, so they
cannot live in a Pydantic schema — a schema only knows the shape of one
request, not whether the condition ids in it belong to the analysis it claims
to review.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.errors import (
    InvalidRequestError,
    NoteNotFoundError,
    ReviewConflictError,
)
from src.models.analysis import Analysis
from src.models.enums import AnalysisStatus, ConditionOrigin, ReviewAction
from src.models.review import Review, ReviewedCondition, ReviewedGap
from src.models.user import AuthenticatedUser
from src.repositories.base import (
    AnalysisRepository,
    NoteRepository,
    ReviewRepository,
)
from src.utils.ids import new_id


class ReviewService:
    def __init__(
        self,
        reviews: ReviewRepository,
        analyses: AnalysisRepository,
        notes: NoteRepository,
    ) -> None:
        self._reviews = reviews
        self._analyses = analyses
        self._notes = notes

    async def submit(
        self,
        caller: AuthenticatedUser,
        analysis_id: str,
        conditions: list[ReviewedCondition],
        gaps: list[ReviewedGap],
        summary_override: str | None,
        reviewer_note: str | None,
    ) -> Review:
        analysis = await self._analyses.get(analysis_id, caller.uid)
        if analysis is None:
            raise ReviewConflictError("The analysis being reviewed was not found.")

        note = await self._notes.get(analysis.note_id, caller.uid)
        if note is None:
            raise NoteNotFoundError

        if note.latest_analysis_id != analysis.analysis_id:
            raise ReviewConflictError(
                "A newer analysis exists for this note. Reload before submitting."
            )

        self._assert_invariants(analysis, conditions)

        next_version = await self._reviews.latest_version_for_analysis(analysis_id, caller.uid) + 1

        review = await self._reviews.create(
            Review(
                review_id=new_id(),
                analysis_id=analysis.analysis_id,
                note_id=analysis.note_id,
                owner_uid=caller.uid,
                version=next_version,
                reviewed_conditions=conditions,
                reviewed_gaps=gaps,
                summary_override=summary_override,
                reviewer_note=reviewer_note,
                created_at=datetime.now(timezone.utc),
            )
        )

        await self._notes.apply_review_result(
            note_id=analysis.note_id,
            owner_uid=caller.uid,
            review_id=review.review_id,
            condition_count=review.accepted_condition_count,
        )
        return review

    async def list_for_analysis(
        self, caller: AuthenticatedUser, analysis_id: str
    ) -> list[Review]:
        return await self._reviews.list_for_analysis(analysis_id, caller.uid)

    def _assert_invariants(
        self, analysis: Analysis, conditions: list[ReviewedCondition]
    ) -> None:
        if analysis.status is not AnalysisStatus.SUCCEEDED:
            raise InvalidRequestError("An analysis without valid output cannot be reviewed.")

        ai_conditions = analysis.output.conditions if analysis.output is not None else []
        known_ids = {condition.condition_id for condition in ai_conditions}
        seen: set[str] = set()

        for condition in conditions:
            if condition.condition_id in seen:
                raise InvalidRequestError(
                    f"Condition {condition.condition_id} appears more than once."
                )
            seen.add(condition.condition_id)
            self._assert_condition_is_coherent(condition, known_ids)

    @staticmethod
    def _assert_condition_is_coherent(
        condition: ReviewedCondition, known_ids: set[str]
    ) -> None:
        """Origin, action and the referenced analysis must agree."""
        is_ai = condition.origin is ConditionOrigin.AI
        is_added = condition.action is ReviewAction.ADDED

        if is_ai and condition.condition_id not in known_ids:
            raise InvalidRequestError(
                "A reviewed condition claims to come from the model but does not "
                "appear in the analysis being reviewed."
            )

        if is_ai == is_added:
            raise InvalidRequestError(
                "Action 'added' belongs to clinician-authored conditions only, and "
                "every clinician-authored condition must use it."
            )

        if condition.action is ReviewAction.REJECTED and not condition.rejection_reason:
            raise InvalidRequestError(
                "Rejecting a condition requires a reason — it is the most useful "
                "signal in the correction dataset."
            )
