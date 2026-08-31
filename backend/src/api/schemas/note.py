from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.schemas.common import RequestBase
from src.core.config import get_settings
from src.models.enums import ReviewStatus
from src.models.note import Note
from src.utils.text import count_words

PSEUDONYM_MAX_LENGTH = 64
REVIEWER_TEXT_MAX_LENGTH = 2000


class CreateNoteRequest(RequestBase):
    """A clinical note submitted for analysis.

    The 100-3000 word range comes from the product specification and both
    bounds are enforced. The character ceiling sits alongside the word maximum
    because a single 40,000-character "word" would pass a word count on its own.

    There is no owner_uid field here, and `extra="forbid"` means one cannot be
    smuggled in: ownership comes from the verified token.
    """

    content: str = Field(min_length=1)
    pseudonym: str | None = Field(default=None, max_length=PSEUDONYM_MAX_LENGTH)
    visit_date: date | None = None

    @field_validator("visit_date")
    @classmethod
    def reject_future_visit_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("The visit date cannot be in the future.")
        return value

    @field_validator("pseudonym")
    @classmethod
    def empty_pseudonym_is_absent(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def enforce_note_length(self) -> "CreateNoteRequest":
        settings = get_settings()

        if len(self.content) > settings.note_max_chars:
            raise ValueError(
                f"The note is {len(self.content)} characters long; "
                f"the maximum is {settings.note_max_chars}."
            )

        words = count_words(self.content)
        if words < settings.note_min_words or words > settings.note_max_words:
            raise ValueError(
                f"The note is {words} words long; it must be between "
                f"{settings.note_min_words} and {settings.note_max_words} words."
            )
        return self


class NoteResponse(BaseModel):
    note_id: str
    content: str
    pseudonym: str | None
    visit_date: date | None
    word_count: int
    created_at: datetime
    updated_at: datetime
    latest_analysis_id: str | None
    latest_review_id: str | None
    review_status: ReviewStatus
    condition_count: int
    analysis_count: int

    @classmethod
    def from_domain(cls, note: Note) -> "NoteResponse":
        return cls(
            note_id=note.note_id,
            content=note.content,
            pseudonym=note.pseudonym,
            visit_date=note.visit_date,
            word_count=note.word_count,
            created_at=note.created_at,
            updated_at=note.updated_at,
            latest_analysis_id=note.latest_analysis_id,
            latest_review_id=note.latest_review_id,
            review_status=note.review_status,
            condition_count=note.condition_count,
            analysis_count=note.analysis_count,
        )


class NoteSummaryResponse(BaseModel):
    """History-list row.

    Deliberately excludes `content`: a list of 20 notes should not ship 60,000
    words to render four columns.
    """

    note_id: str
    pseudonym: str | None
    visit_date: date | None
    created_at: datetime
    word_count: int
    condition_count: int
    analysis_count: int
    review_status: ReviewStatus

    @classmethod
    def from_domain(cls, note: Note) -> "NoteSummaryResponse":
        return cls(
            note_id=note.note_id,
            pseudonym=note.pseudonym,
            visit_date=note.visit_date,
            created_at=note.created_at,
            word_count=note.word_count,
            condition_count=note.condition_count,
            analysis_count=note.analysis_count,
            review_status=note.review_status,
        )
