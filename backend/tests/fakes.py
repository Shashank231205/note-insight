"""In-memory implementations of the repository protocols and the token verifier.

These let the API suite exercise real routes, real services and real ownership
logic without an emulator or a network. They are test doubles for storage only:
no business rule is reimplemented here.
"""

from __future__ import annotations

from src.core.errors import NoteNotFoundError, TokenInvalidError
from src.models.analysis import Analysis
from src.models.enums import AnalysisStatus, ReviewStatus
from src.models.note import Note
from src.models.review import Review
from src.models.user import AuthenticatedUser, User
from src.repositories.base import Cursor, Page


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.documents: dict[str, User] = {}

    async def get(self, uid: str) -> User | None:
        return self.documents.get(uid)

    async def upsert(self, user: User) -> User:
        self.documents[user.uid] = user
        return user


class InMemoryNoteRepository:
    def __init__(self) -> None:
        self.documents: dict[str, Note] = {}

    async def create(self, note: Note) -> Note:
        self.documents[note.note_id] = note
        return note

    async def get(self, note_id: str, owner_uid: str) -> Note | None:
        note = self.documents.get(note_id)
        return note if note is not None and note.owner_uid == owner_uid else None

    async def list_for_owner(self, owner_uid: str, limit: int, cursor: Cursor | None) -> Page[Note]:
        owned = sorted(
            (note for note in self.documents.values() if note.owner_uid == owner_uid),
            key=lambda note: (note.created_at, note.note_id),
            reverse=True,
        )
        if cursor is not None:
            owned = [
                note
                for note in owned
                if (note.created_at, note.note_id) < (cursor.created_at, cursor.document_id)
            ]

        page = owned[:limit]
        has_more = len(owned) > limit
        next_cursor = (
            Cursor(created_at=page[-1].created_at, document_id=page[-1].note_id)
            if has_more and page
            else None
        )
        return Page(items=page, next_cursor=next_cursor)

    async def apply_analysis_result(
        self, note_id: str, owner_uid: str, analysis_id: str, condition_count: int
    ) -> Note:
        note = await self._owned_or_raise(note_id, owner_uid)
        updated = note.model_copy(
            update={
                "latest_analysis_id": analysis_id,
                "condition_count": condition_count,
                "analysis_count": note.analysis_count + 1,
            }
        )
        self.documents[note_id] = updated
        return updated

    async def apply_review_result(
        self, note_id: str, owner_uid: str, review_id: str, condition_count: int
    ) -> Note:
        note = await self._owned_or_raise(note_id, owner_uid)
        updated = note.model_copy(
            update={
                "latest_review_id": review_id,
                "review_status": ReviewStatus.REVIEWED,
                "condition_count": condition_count,
            }
        )
        self.documents[note_id] = updated
        return updated

    async def _owned_or_raise(self, note_id: str, owner_uid: str) -> Note:
        note = await self.get(note_id, owner_uid)
        if note is None:
            raise NoteNotFoundError
        return note


class InMemoryAnalysisRepository:
    def __init__(self) -> None:
        self.documents: dict[str, Analysis] = {}

    async def create(self, analysis: Analysis) -> Analysis:
        self.documents[analysis.analysis_id] = analysis
        return analysis

    async def get(self, analysis_id: str, owner_uid: str) -> Analysis | None:
        analysis = self.documents.get(analysis_id)
        return analysis if analysis is not None and analysis.owner_uid == owner_uid else None

    async def list_for_note(self, note_id: str, owner_uid: str) -> list[Analysis]:
        return sorted(
            (
                analysis
                for analysis in self.documents.values()
                if analysis.note_id == note_id and analysis.owner_uid == owner_uid
            ),
            key=lambda analysis: analysis.created_at,
            reverse=True,
        )

    async def find_cached(
        self, owner_uid: str, content_hash: str, prompt_version: str, model_id: str
    ) -> Analysis | None:
        matches = sorted(
            (
                analysis
                for analysis in self.documents.values()
                if analysis.owner_uid == owner_uid
                and analysis.content_hash == content_hash
                and analysis.prompt_version == prompt_version
                and analysis.model_id == model_id
                and analysis.status is AnalysisStatus.SUCCEEDED
            ),
            key=lambda analysis: analysis.created_at,
            reverse=True,
        )
        return matches[0] if matches else None


class InMemoryReviewRepository:
    def __init__(self) -> None:
        self.documents: dict[str, Review] = {}

    async def create(self, review: Review) -> Review:
        self.documents[review.review_id] = review
        return review

    async def get(self, review_id: str, owner_uid: str) -> Review | None:
        review = self.documents.get(review_id)
        return review if review is not None and review.owner_uid == owner_uid else None

    async def list_for_analysis(self, analysis_id: str, owner_uid: str) -> list[Review]:
        return sorted(
            (
                review
                for review in self.documents.values()
                if review.analysis_id == analysis_id and review.owner_uid == owner_uid
            ),
            key=lambda review: review.version,
            reverse=True,
        )

    async def latest_version_for_analysis(self, analysis_id: str, owner_uid: str) -> int:
        versions = await self.list_for_analysis(analysis_id, owner_uid)
        return versions[0].version if versions else 0


class FakeTokenVerifier:
    """Maps opaque test tokens to identities.

    Any token not registered is rejected, so "unauthenticated" and "bad token"
    are both exercised the way the real verifier would treat them.
    """

    def __init__(self) -> None:
        self.identities: dict[str, AuthenticatedUser] = {}

    def register(self, token: str, uid: str, email: str) -> AuthenticatedUser:
        identity = AuthenticatedUser(uid=uid, email=email, email_verified=True)
        self.identities[token] = identity
        return identity

    def verify(self, id_token: str) -> AuthenticatedUser:
        identity = self.identities.get(id_token)
        if identity is None:
            raise TokenInvalidError
        return identity
