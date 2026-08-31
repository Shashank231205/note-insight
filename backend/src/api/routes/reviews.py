from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.services import get_review_service
from src.api.schemas.review import ReviewResponse, SubmitReviewRequest
from src.models.review import ReviewedCondition, ReviewedGap
from src.models.user import AuthenticatedUser
from src.services.review.review_service import ReviewService

router = APIRouter(prefix="/analyses", tags=["reviews"])


@router.post(
    "/{analysis_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_review(
    analysis_id: str,
    payload: SubmitReviewRequest,
    caller: AuthenticatedUser = Depends(get_current_user),
    reviews: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    """Record the clinician's corrections as a new review version.

    The analysis is never mutated. Asking "what did the model say, and what did
    the human change?" is a diff between the two documents.
    """
    review = await reviews.submit(
        caller,
        analysis_id=analysis_id,
        conditions=[
            ReviewedCondition(
                condition_id=item.condition_id,
                origin=item.origin,
                action=item.action,
                name=item.name,
                evidence_quote=item.evidence_quote,
                documentation_status=item.documentation_status,
                icd10_code=item.icd10_code,
                rejection_reason=item.rejection_reason,
            )
            for item in payload.reviewed_conditions
        ],
        gaps=[
            ReviewedGap(
                gap_id=item.gap_id,
                origin=item.origin,
                action=item.action,
                description=item.description,
            )
            for item in payload.reviewed_gaps
        ],
        summary_override=payload.summary_override,
        reviewer_note=payload.reviewer_note,
    )
    return ReviewResponse.from_domain(review)


@router.get("/{analysis_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    analysis_id: str,
    caller: AuthenticatedUser = Depends(get_current_user),
    reviews: ReviewService = Depends(get_review_service),
) -> list[ReviewResponse]:
    """Every review version for this analysis, newest first."""
    history = await reviews.list_for_analysis(caller, analysis_id)
    return [ReviewResponse.from_domain(review) for review in history]
