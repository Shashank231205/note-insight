"""Translation from domain errors to HTTP responses.

The only module that knows about both the domain exception hierarchy and
FastAPI. Services never import HTTPException.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.schemas.common import ErrorDetail, ErrorResponse
from src.core.errors import DomainError, ErrorCode, RateLimitedError
from src.core.logger import get_logger, get_request_id, log_context

logger = get_logger(__name__)


def _envelope(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=get_request_id(),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


async def handle_domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    headers = None
    if isinstance(exc, RateLimitedError):
        headers = {"Retry-After": str(exc.retry_after_seconds)}

    logger.warning(
        "domain_error",
        extra=log_context(error_code=exc.code.value, status_code=exc.status_code),
    )
    return _envelope(exc.status_code, exc.code.value, exc.message, headers=headers)


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"][1:]) or "body",
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    logger.info("request_validation_failed", extra=log_context(field_count=len(details)))
    return _envelope(
        422,
        ErrorCode.VALIDATION_ERROR.value,
        "The request contains invalid values.",
        details=details,
    )


async def handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    known: dict[int, tuple[ErrorCode, str]] = {
        401: (ErrorCode.UNAUTHENTICATED, "Authentication is required."),
        403: (ErrorCode.FORBIDDEN, "This action is not permitted."),
        404: (ErrorCode.NOT_FOUND, "The requested resource was not found."),
        405: (ErrorCode.METHOD_NOT_ALLOWED, "This method is not allowed for this resource."),
    }
    code, message = known.get(exc.status_code, (ErrorCode.INVALID_REQUEST, str(exc.detail)))
    return _envelope(exc.status_code, code.value, message)


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    """Last resort. The exception detail goes to the log, never to the client."""
    logger.exception("unhandled_exception", extra=log_context(exception_type=type(exc).__name__))
    return _envelope(
        500,
        ErrorCode.INTERNAL_ERROR.value,
        "An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
