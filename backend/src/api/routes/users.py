from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.services import get_user_service
from src.api.schemas.user import UserResponse
from src.models.user import AuthenticatedUser
from src.services.auth.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    caller: AuthenticatedUser = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> UserResponse:
    """Return the caller's profile, creating the mirror document on first call."""
    profile = await users.get_or_create_profile(caller)
    return UserResponse.from_domain(profile)
