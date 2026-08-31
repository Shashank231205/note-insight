"""Domain exceptions.

Services and repositories raise these. They carry no HTTP knowledge — the
translation to status codes and response bodies happens in exception_handlers,
which is the only module that imports both this file and FastAPI.
"""

from enum import Enum


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"

    UNAUTHENTICATED = "UNAUTHENTICATED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    FORBIDDEN = "FORBIDDEN"

    NOTE_NOT_FOUND = "NOTE_NOT_FOUND"
    ANALYSIS_NOT_FOUND = "ANALYSIS_NOT_FOUND"
    REVIEW_NOT_FOUND = "REVIEW_NOT_FOUND"

    REVIEW_CONFLICT = "REVIEW_CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"

    PROVIDER_INVALID_OUTPUT = "PROVIDER_INVALID_OUTPUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """Base class for every expected failure in the application."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class InvalidRequestError(DomainError):
    code = ErrorCode.INVALID_REQUEST
    status_code = 400
    message = "The request could not be processed."


class UnauthenticatedError(DomainError):
    code = ErrorCode.UNAUTHENTICATED
    status_code = 401
    message = "Authentication is required."


class TokenExpiredError(DomainError):
    code = ErrorCode.TOKEN_EXPIRED
    status_code = 401
    message = "The session has expired. Please sign in again."


class TokenInvalidError(DomainError):
    code = ErrorCode.TOKEN_INVALID
    status_code = 401
    message = "The authentication token is not valid."


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN
    status_code = 403
    message = "This action is not permitted."


class ResourceNotFoundError(DomainError):
    status_code = 404
    message = "The requested resource was not found."


class NoteNotFoundError(ResourceNotFoundError):
    code = ErrorCode.NOTE_NOT_FOUND
    message = "Note not found."


class AnalysisNotFoundError(ResourceNotFoundError):
    code = ErrorCode.ANALYSIS_NOT_FOUND
    message = "Analysis not found."


class ReviewNotFoundError(ResourceNotFoundError):
    code = ErrorCode.REVIEW_NOT_FOUND
    message = "Review not found."


class ReviewConflictError(DomainError):
    code = ErrorCode.REVIEW_CONFLICT
    status_code = 409
    message = "This analysis is no longer the most recent one for the note."


class RateLimitedError(DomainError):
    code = ErrorCode.RATE_LIMITED
    status_code = 429
    message = "Analysis rate limit reached. Please try again later."

    def __init__(self, retry_after_seconds: int, message: str | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class ProviderInvalidOutputError(DomainError):
    code = ErrorCode.PROVIDER_INVALID_OUTPUT
    status_code = 502
    message = "The analysis model returned output that could not be validated."


class ProviderUnavailableError(DomainError):
    code = ErrorCode.PROVIDER_UNAVAILABLE
    status_code = 503
    message = "The analysis service is temporarily unavailable. Please try again."
