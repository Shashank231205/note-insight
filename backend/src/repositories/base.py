"""Repository interfaces and pagination helpers.

Services depend on these protocols, not on Firestore. That keeps the persistence
choice replaceable (the README argues Postgres would be the right migration if
reporting requirements grew) and lets the test suite run against in-memory
fakes with no emulator and no network.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Protocol, TypeVar

from src.core.errors import InvalidRequestError
from src.models.analysis import Analysis
from src.models.note import Note
from src.models.review import Review
from src.models.user import User

ItemT = TypeVar("ItemT")

CURSOR_SEPARATOR = "|"


@dataclass(frozen=True)
class Cursor:
    """Position in a `created_at DESC, id DESC` ordering.

    Keyset pagination rather than offset: Firestore bills for every document an
    offset skips, so offsets get more expensive the deeper a user scrolls.
    """

    created_at: datetime
    document_id: str

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}{CURSOR_SEPARATOR}{self.document_id}"
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    @classmethod
    def decode(cls, value: str) -> Cursor:
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
            timestamp, _, document_id = raw.partition(CURSOR_SEPARATOR)
            if not document_id:
                raise ValueError("cursor is missing a document id")
            return cls(created_at=datetime.fromisoformat(timestamp), document_id=document_id)
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise InvalidRequestError("The pagination cursor is not valid.") from exc


@dataclass(frozen=True)
class Page(Generic[ItemT]):
    items: list[ItemT]
    next_cursor: Cursor | None


class UserRepository(Protocol):
    async def get(self, uid: str) -> User | None: ...

    async def upsert(self, user: User) -> User: ...


class NoteRepository(Protocol):
    async def create(self, note: Note) -> Note: ...

    async def get(self, note_id: str, owner_uid: str) -> Note | None:
        """Ownership is a query predicate, not a post-fetch check."""
        ...

    async def list_for_owner(
        self, owner_uid: str, limit: int, cursor: Cursor | None
    ) -> Page[Note]: ...

    async def apply_analysis_result(
        self, note_id: str, owner_uid: str, analysis_id: str, condition_count: int
    ) -> Note: ...

    async def apply_review_result(
        self, note_id: str, owner_uid: str, review_id: str, condition_count: int
    ) -> Note: ...


class AnalysisRepository(Protocol):
    async def create(self, analysis: Analysis) -> Analysis: ...

    async def get(self, analysis_id: str, owner_uid: str) -> Analysis | None: ...

    async def list_for_note(self, note_id: str, owner_uid: str) -> list[Analysis]: ...

    async def find_cached(
        self, owner_uid: str, content_hash: str, prompt_version: str, model_id: str
    ) -> Analysis | None:
        """Most recent succeeded analysis for an identical note and prompt."""
        ...


class ReviewRepository(Protocol):
    async def create(self, review: Review) -> Review: ...

    async def get(self, review_id: str, owner_uid: str) -> Review | None: ...

    async def list_for_analysis(self, analysis_id: str, owner_uid: str) -> list[Review]: ...

    async def latest_version_for_analysis(self, analysis_id: str, owner_uid: str) -> int: ...
