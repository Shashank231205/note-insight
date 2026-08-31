from __future__ import annotations

import asyncio

from google.cloud.firestore import Client as FirestoreClient

from src.models.user import User
from src.repositories.firestore_mapping import document_to_user, user_to_document

COLLECTION = "users"


class FirestoreUserRepository:
    def __init__(self, client: FirestoreClient) -> None:
        self._client = client

    async def get(self, uid: str) -> User | None:
        def _read() -> User | None:
            snapshot = self._client.collection(COLLECTION).document(uid).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict()
            return document_to_user(data) if data is not None else None

        return await asyncio.to_thread(_read)

    async def upsert(self, user: User) -> User:
        def _write() -> None:
            self._client.collection(COLLECTION).document(user.uid).set(
                user_to_document(user), merge=True
            )

        await asyncio.to_thread(_write)
        return user
