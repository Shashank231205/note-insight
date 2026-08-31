from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, str]] | None = None
    request_id: str


class ErrorResponse(BaseModel):
    """The single response shape for every non-2xx status."""

    error: ErrorDetail


class PageResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    next_cursor: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


class RequestBase(BaseModel):
    """Base for every request body.

    `extra="forbid"` is what stops a client smuggling fields the contract does
    not declare — owner_uid above all.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = None
