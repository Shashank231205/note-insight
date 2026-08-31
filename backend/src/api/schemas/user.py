from datetime import datetime

from pydantic import BaseModel

from src.models.user import User


class UserResponse(BaseModel):
    uid: str
    email: str
    display_name: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
        )
