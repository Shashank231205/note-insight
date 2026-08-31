from __future__ import annotations

import asyncio

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Query

from src.models.analysis import Analysis
from src.models.enums import AnalysisStatus
from src.repositories.firestore_mapping import analysis_to_document, document_to_analysis

COLLECTION = "analyses"


class FirestoreAnalysisRepository:
    """Analyses are append-only. There is no update method, by design."""

    def __init__(self, client: FirestoreClient) -> None:
        self._client = client

    async def create(self, analysis: Analysis) -> Analysis:
        def _write() -> None:
            self._client.collection(COLLECTION).document(analysis.analysis_id).set(
                analysis_to_document(analysis)
            )

        await asyncio.to_thread(_write)
        return analysis

    async def get(self, analysis_id: str, owner_uid: str) -> Analysis | None:
        def _read() -> Analysis | None:
            snapshot = self._client.collection(COLLECTION).document(analysis_id).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            if data is None or data.get("owner_uid") != owner_uid:
                return None
            return document_to_analysis(data)

        return await asyncio.to_thread(_read)

    async def list_for_note(self, note_id: str, owner_uid: str) -> list[Analysis]:
        def _query() -> list[Analysis]:
            snapshots = (
                self._client.collection(COLLECTION)
                .where("owner_uid", "==", owner_uid)
                .where("note_id", "==", note_id)
                .order_by("created_at", direction=Query.DESCENDING)
                .stream()
            )
            return [
                document_to_analysis(data)
                for snapshot in snapshots
                if (data := snapshot.to_dict()) is not None
            ]

        return await asyncio.to_thread(_query)

    async def find_cached(
        self, owner_uid: str, content_hash: str, prompt_version: str, model_id: str
    ) -> Analysis | None:
        """Most recent successful analysis of identical text under the same prompt.

        Scoped to the owner as well as the content: one clinician's analysis is
        not served to another, even for byte-identical text.
        """

        def _query() -> Analysis | None:
            snapshots = list(
                self._client.collection(COLLECTION)
                .where("owner_uid", "==", owner_uid)
                .where("content_hash", "==", content_hash)
                .where("prompt_version", "==", prompt_version)
                .where("model_id", "==", model_id)
                .where("status", "==", AnalysisStatus.SUCCEEDED.value)
                .order_by("created_at", direction=Query.DESCENDING)
                .limit(1)
                .stream()
            )
            if not snapshots:
                return None
            data = snapshots[0].to_dict()
            return document_to_analysis(data) if data is not None else None

        return await asyncio.to_thread(_query)
