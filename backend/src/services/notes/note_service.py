from datetime import date, datetime, timezone

from src.core.errors import NoteNotFoundError
from src.models.note import Note
from src.models.user import AuthenticatedUser
from src.repositories.base import Cursor, NoteRepository, Page
from src.utils.hashing import content_fingerprint
from src.utils.ids import new_id
from src.utils.text import count_words


class NoteService:
    """Owns the note lifecycle.

    Every method takes the verified caller rather than a uid string, so a
    caller id can only enter this layer having come from a verified token.
    """

    def __init__(self, notes: NoteRepository) -> None:
        self._notes = notes

    async def create(
        self,
        caller: AuthenticatedUser,
        content: str,
        pseudonym: str | None,
        visit_date: date | None,
    ) -> Note:
        now = datetime.now(timezone.utc)
        return await self._notes.create(
            Note(
                note_id=new_id(),
                owner_uid=caller.uid,
                content=content,
                content_hash=content_fingerprint(content),
                word_count=count_words(content),
                pseudonym=pseudonym,
                visit_date=visit_date,
                created_at=now,
                updated_at=now,
            )
        )

    async def get_owned(self, caller: AuthenticatedUser, note_id: str) -> Note:
        """Return the caller's note, or raise not-found.

        A note belonging to someone else is reported as missing rather than
        forbidden: a 403 would confirm the note exists.
        """
        note = await self._notes.get(note_id, caller.uid)
        if note is None:
            raise NoteNotFoundError
        return note

    async def list_history(
        self, caller: AuthenticatedUser, limit: int, cursor: Cursor | None
    ) -> Page[Note]:
        return await self._notes.list_for_owner(caller.uid, limit, cursor)
