from __future__ import annotations

import asyncio

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Query

from src.models.review import Review
from src.repositories.firestore_mapping import document_to_review, review_to_document

COLLECTION = "reviews"


class FirestoreReviewRepository:
    """Reviews are versioned, never updated in place."""

    def __init__(self, client: FirestoreClient) -> None:
        self._client = client

    async def create(self, review: Review) -> Review:
        def _write() -> None:
            self._client.collection(COLLECTION).document(review.review_id).set(
                review_to_document(review)
            )

        await asyncio.to_thread(_write)
        return review

    async def get(self, review_id: str, owner_uid: str) -> Review | None:
        def _read() -> Review | None:
            snapshot = self._client.collection(COLLECTION).document(review_id).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            if data is None or data.get("owner_uid") != owner_uid:
                return None
            return document_to_review(data)

        return await asyncio.to_thread(_read)

    async def list_for_analysis(self, analysis_id: str, owner_uid: str) -> list[Review]:
        def _query() -> list[Review]:
            snapshots = (
                self._client.collection(COLLECTION)
                .where("owner_uid", "==", owner_uid)
                .where("analysis_id", "==", analysis_id)
                .order_by("version", direction=Query.DESCENDING)
                .stream()
            )
            return [
                document_to_review(data)
                for snapshot in snapshots
                if (data := snapshot.to_dict()) is not None
            ]

        return await asyncio.to_thread(_query)

    async def latest_version_for_analysis(self, analysis_id: str, owner_uid: str) -> int:
        def _query() -> int:
            snapshots = list(
                self._client.collection(COLLECTION)
                .where("owner_uid", "==", owner_uid)
                .where("analysis_id", "==", analysis_id)
                .order_by("version", direction=Query.DESCENDING)
                .limit(1)
                .stream()
            )
            if not snapshots:
                return 0
            data = snapshots[0].to_dict()
            version = data.get("version") if data is not None else None
            return version if isinstance(version, int) else 0

        return await asyncio.to_thread(_query)
