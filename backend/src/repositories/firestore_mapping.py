"""Conversion between domain models and Firestore documents.

Kept in one module so the storage representation is described in a single
place. Firestore returns timezone-aware datetimes and its own DatetimeWithNanos
type; `date` has no native representation and is stored as an ISO string.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone

from src.models.analysis import Analysis
from src.models.note import Note
from src.models.review import Review
from src.models.user import User

DocumentData = dict[str, object]


def _to_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    raise TypeError(f"Expected a datetime, received {type(value).__name__}.")


def _to_optional_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(value, datetime):
        return value.date()
    raise TypeError(f"Expected an ISO date string, received {type(value).__name__}.")


def note_to_document(note: Note) -> DocumentData:
    document = note.model_dump(mode="json")
    document["created_at"] = note.created_at
    document["updated_at"] = note.updated_at
    return document


def document_to_note(data: Mapping[str, object]) -> Note:
    payload = dict(data)
    payload["created_at"] = _to_utc(payload["created_at"])
    payload["updated_at"] = _to_utc(payload["updated_at"])
    payload["visit_date"] = _to_optional_date(payload.get("visit_date"))
    return Note.model_validate(payload)


def analysis_to_document(analysis: Analysis) -> DocumentData:
    document = analysis.model_dump(mode="json")
    document["created_at"] = analysis.created_at
    if analysis.verification is not None:
        verification = document["verification"]
        assert isinstance(verification, dict)
        verification["checked_at"] = analysis.verification.checked_at
    return document


def document_to_analysis(data: Mapping[str, object]) -> Analysis:
    payload = dict(data)
    payload["created_at"] = _to_utc(payload["created_at"])
    verification = payload.get("verification")
    if isinstance(verification, dict):
        verification["checked_at"] = _to_utc(verification["checked_at"])
    return Analysis.model_validate(payload)


def review_to_document(review: Review) -> DocumentData:
    document = review.model_dump(mode="json")
    document["created_at"] = review.created_at
    return document


def document_to_review(data: Mapping[str, object]) -> Review:
    payload = dict(data)
    payload["created_at"] = _to_utc(payload["created_at"])
    return Review.model_validate(payload)


def user_to_document(user: User) -> DocumentData:
    document = user.model_dump(mode="json")
    document["created_at"] = user.created_at
    document["last_seen_at"] = user.last_seen_at
    return document


def document_to_user(data: Mapping[str, object]) -> User:
    payload = dict(data)
    payload["created_at"] = _to_utc(payload["created_at"])
    payload["last_seen_at"] = _to_utc(payload["last_seen_at"])
    return User.model_validate(payload)
