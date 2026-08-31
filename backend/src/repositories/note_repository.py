"""Firestore persistence for notes.

Every read is scoped by owner_uid. Fetch-then-check is deliberately avoided in
the query paths: a query that cannot express itself without the ownership
predicate is structurally safer than one relying on a caller to remember.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import DocumentReference, Query, Transaction, transactional

from src.core.errors import NoteNotFoundError
from src.models.enums import ReviewStatus
from src.models.note import Note
from src.repositories.base import Cursor, Page
from src.repositories.firestore_mapping import document_to_note, note_to_document

COLLECTION = "notes"


@transactional
def _update_note_transaction(
    transaction: Transaction,
    reference: DocumentReference,
    owner_uid: str,
    changes: Mapping[str, object],
    increment_analysis_count: bool,
) -> Note:
    snapshot = reference.get(transaction=transaction)
    data = snapshot.to_dict() if snapshot.exists else None
    if data is None or data.get("owner_uid") != owner_uid:
        raise NoteNotFoundError

    updates = dict(changes)
    if increment_analysis_count:
        current = data.get("analysis_count")
        updates["analysis_count"] = (current if isinstance(current, int) else 0) + 1

    transaction.update(reference, updates)
    return document_to_note({**data, **updates})


class FirestoreNoteRepository:
    def __init__(self, client: FirestoreClient) -> None:
        self._client = client

    async def create(self, note: Note) -> Note:
        def _write() -> None:
            self._client.collection(COLLECTION).document(note.note_id).set(note_to_document(note))

        await asyncio.to_thread(_write)
        return note

    async def get(self, note_id: str, owner_uid: str) -> Note | None:
        def _read() -> Note | None:
            snapshot = self._client.collection(COLLECTION).document(note_id).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            if data is None or data.get("owner_uid") != owner_uid:
                return None
            return document_to_note(data)

        return await asyncio.to_thread(_read)

    async def list_for_owner(self, owner_uid: str, limit: int, cursor: Cursor | None) -> Page[Note]:
        def _query() -> Page[Note]:
            query = (
                self._client.collection(COLLECTION)
                .where("owner_uid", "==", owner_uid)
                .order_by("created_at", direction=Query.DESCENDING)
                .order_by("note_id", direction=Query.DESCENDING)
            )
            if cursor is not None:
                query = query.start_after(
                    {"created_at": cursor.created_at, "note_id": cursor.document_id}
                )

            # Fetch one extra document: it tells us whether another page exists
            # without paying for a second count query.
            snapshots = list(query.limit(limit + 1).stream())
            has_more = len(snapshots) > limit
            notes = [
                document_to_note(data)
                for snapshot in snapshots[:limit]
                if (data := snapshot.to_dict()) is not None
            ]
            next_cursor = (
                Cursor(created_at=notes[-1].created_at, document_id=notes[-1].note_id)
                if has_more and notes
                else None
            )
            return Page(items=notes, next_cursor=next_cursor)

        return await asyncio.to_thread(_query)

    async def apply_analysis_result(
        self, note_id: str, owner_uid: str, analysis_id: str, condition_count: int
    ) -> Note:
        return await self._update_derived_fields(
            note_id,
            owner_uid,
            {
                "latest_analysis_id": analysis_id,
                "condition_count": condition_count,
                "updated_at": datetime.now(timezone.utc),
            },
            increment_analysis_count=True,
        )

    async def apply_review_result(
        self, note_id: str, owner_uid: str, review_id: str, condition_count: int
    ) -> Note:
        return await self._update_derived_fields(
            note_id,
            owner_uid,
            {
                "latest_review_id": review_id,
                "review_status": ReviewStatus.REVIEWED.value,
                "condition_count": condition_count,
                "updated_at": datetime.now(timezone.utc),
            },
            increment_analysis_count=False,
        )

    async def _update_derived_fields(
        self,
        note_id: str,
        owner_uid: str,
        changes: Mapping[str, object],
        increment_analysis_count: bool,
    ) -> Note:
        """Update derived counters inside a transaction.

        These are derived values, so an interleaved second analysis would
        otherwise be able to lose an increment.
        """

        def _transact() -> Note:
            reference = self._client.collection(COLLECTION).document(note_id)
            # The firestore @transactional decorator is untyped, so the result
            # is narrowed explicitly rather than trusted.
            updated: object = _update_note_transaction(
                self._client.transaction(),
                reference,
                owner_uid,
                changes,
                increment_analysis_count,
            )
            assert isinstance(updated, Note)
            return updated

        return await asyncio.to_thread(_transact)
