from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.services import get_note_service
from src.api.schemas.common import PageResponse
from src.api.schemas.note import CreateNoteRequest, NoteResponse, NoteSummaryResponse
from src.models.user import AuthenticatedUser
from src.repositories.base import Cursor
from src.services.notes.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: CreateNoteRequest,
    caller: AuthenticatedUser = Depends(get_current_user),
    notes: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Persist a note. Analysis is a separate call so the note survives a
    provider outage."""
    note = await notes.create(
        caller,
        content=payload.content,
        pseudonym=payload.pseudonym,
        visit_date=payload.visit_date,
    )
    return NoteResponse.from_domain(note)


@router.get("", response_model=PageResponse[NoteSummaryResponse])
async def list_notes(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    caller: AuthenticatedUser = Depends(get_current_user),
    notes: NoteService = Depends(get_note_service),
) -> PageResponse[NoteSummaryResponse]:
    """The caller's notes, newest first."""
    page = await notes.list_history(
        caller,
        limit=limit,
        cursor=Cursor.decode(cursor) if cursor else None,
    )
    return PageResponse(
        items=[NoteSummaryResponse.from_domain(note) for note in page.items],
        next_cursor=page.next_cursor.encode() if page.next_cursor else None,
    )


@router.get("/{note_id}", response_model=NoteResponse)
async def read_note(
    note_id: str,
    caller: AuthenticatedUser = Depends(get_current_user),
    notes: NoteService = Depends(get_note_service),
) -> NoteResponse:
    note = await notes.get_owned(caller, note_id)
    return NoteResponse.from_domain(note)
