from fastapi import APIRouter, Depends

from src.api.dependencies.settings import get_request_settings
from src.api.schemas.common import HealthResponse
from src.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_request_settings)) -> HealthResponse:
    """Unauthenticated liveness probe.

    Also the endpoint the frontend pings on mount to wake a cold Render
    instance while the user is still typing their password.
    """
    return HealthResponse(status="ok", version=settings.api_version)
