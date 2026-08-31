from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.rate_limit import (
    TokenBucketRateLimiter,
    enforce_analysis_rate_limit,
    get_rate_limiter,
)
from src.api.dependencies.services import get_analysis_service, get_note_service
from src.api.schemas.analysis import AnalysisResponse, RunAnalysisRequest
from src.models.user import AuthenticatedUser
from src.services.analysis.analysis_service import AnalysisService
from src.services.notes.note_service import NoteService

note_scoped_router = APIRouter(prefix="/notes", tags=["analyses"])
analysis_router = APIRouter(prefix="/analyses", tags=["analyses"])


@note_scoped_router.post(
    "/{note_id}/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_analysis(
    note_id: str,
    payload: RunAnalysisRequest,
    caller: AuthenticatedUser = Depends(get_current_user),
    notes: NoteService = Depends(get_note_service),
    analyses: AnalysisService = Depends(get_analysis_service),
    limiter: TokenBucketRateLimiter = Depends(get_rate_limiter),
) -> AnalysisResponse:
    """Analyze a note.

    A 201 with status `invalid_output` means the model answered but we could
    not trust the answer — a real event we recorded. A 503 means we never
    reached the model, so nothing was created. The UI tells those apart.
    """
    enforce_analysis_rate_limit(caller, limiter)
    note = await notes.get_owned(caller, note_id)
    analysis = await analyses.analyze(caller, note, force=payload.force)
    return AnalysisResponse.from_domain(analysis)


@note_scoped_router.get("/{note_id}/analyses", response_model=list[AnalysisResponse])
async def list_analyses_for_note(
    note_id: str,
    caller: AuthenticatedUser = Depends(get_current_user),
    notes: NoteService = Depends(get_note_service),
    analyses: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisResponse]:
    """Every analysis of this note, newest first — the prompt-iteration trail."""
    note = await notes.get_owned(caller, note_id)
    history = await analyses.list_for_note(caller, note.note_id)
    return [AnalysisResponse.from_domain(analysis) for analysis in history]


@analysis_router.get("/{analysis_id}", response_model=AnalysisResponse)
async def read_analysis(
    analysis_id: str,
    caller: AuthenticatedUser = Depends(get_current_user),
    analyses: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    analysis = await analyses.get_owned(caller, analysis_id)
    return AnalysisResponse.from_domain(analysis)
