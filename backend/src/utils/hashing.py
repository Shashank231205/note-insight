import hashlib

from src.utils.text import collapse_whitespace


def content_fingerprint(content: str) -> str:
    """Stable hash of a note's text, used as the analysis cache key.

    Whitespace is collapsed first so that a note re-pasted with different line
    wrapping is recognised as the same note rather than paid for twice.
    """
    return hashlib.sha256(collapse_whitespace(content).encode("utf-8")).hexdigest()
