from datetime import datetime, timezone

import pytest

from src.core.errors import InvalidRequestError
from src.repositories.base import Cursor


def test_cursor_survives_a_round_trip() -> None:
    original = Cursor(created_at=datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc), document_id="abc")

    assert Cursor.decode(original.encode()) == original


def test_malformed_cursor_is_a_client_error_not_a_crash() -> None:
    with pytest.raises(InvalidRequestError):
        Cursor.decode("not-a-real-cursor")


def test_cursor_without_a_document_id_is_rejected() -> None:
    import base64

    encoded = base64.urlsafe_b64encode(b"2026-03-01T09:30:00+00:00").decode("ascii")

    with pytest.raises(InvalidRequestError):
        Cursor.decode(encoded)


def test_cursor_with_an_unparseable_timestamp_is_rejected() -> None:
    import base64

    encoded = base64.urlsafe_b64encode(b"not-a-date|abc").decode("ascii")

    with pytest.raises(InvalidRequestError):
        Cursor.decode(encoded)
