from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.models.enums import ReviewStatus


class Note(BaseModel):
    """A clinical note as written by the clinician. The immutable input.

    The trailing fields are denormalized so the history list renders from a
    single query with no fan-out reads. They are derived values with exactly
    one writer (NoteService), so they cannot drift from two directions.
    """

    model_config = ConfigDict(frozen=True)

    note_id: str
    owner_uid: str

    content: str
    content_hash: str
    word_count: int

    pseudonym: str | None
    visit_date: date | None

    created_at: datetime
    updated_at: datetime

    latest_analysis_id: str | None = None
    latest_review_id: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    condition_count: int = 0
    analysis_count: int = 0
