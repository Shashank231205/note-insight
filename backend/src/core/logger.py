"""Structured JSON logging with per-request correlation.

Clinical note content is never logged. Identifiers, hashes, counts and timings
are — enough to debug a failure, never enough to reconstruct a note from log
storage.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str:
    return _request_id.get()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "google", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.LoggerAdapter[logging.Logger]:
    return logging.LoggerAdapter(logging.getLogger(name), {})


def log_context(**fields: object) -> Mapping[str, object]:
    """Build the `extra` mapping for a log call, dropping empty values."""
    return {key: value for key, value in fields.items() if value is not None}
