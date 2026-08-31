from datetime import datetime, timezone

from src.models.user import AuthenticatedUser, User
from src.repositories.base import UserRepository


class UserService:
    """Keeps the Firestore user mirror in step with the Firebase identity.

    Credentials stay in Firebase Auth. This document exists only so notes and
    reviews can be attributed without an Auth API call on every request.
    """

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def get_or_create_profile(self, caller: AuthenticatedUser) -> User:
        now = datetime.now(timezone.utc)
        existing = await self._users.get(caller.uid)

        if existing is None:
            return await self._users.upsert(
                User(
                    uid=caller.uid,
                    email=caller.email,
                    display_name=None,
                    created_at=now,
                    last_seen_at=now,
                )
            )

        return await self._users.upsert(
            existing.model_copy(update={"email": caller.email, "last_seen_at": now})
        )
