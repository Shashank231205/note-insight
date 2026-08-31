"""Versioned prompt loading.

Prompts are files, not string literals, so they are reviewable in a diff. The
version is recorded on every analysis and forms part of the cache key, which is
what makes "the same note under a new prompt" a new analysis rather than a
cache hit.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_DIRECTORY = Path(__file__).parent
NOTE_PLACEHOLDER = "{note_content}"

# Older versions stay registered: analyses recorded under them remain
# reproducible, and the version is part of the cache key, so a prompt change
# must arrive as a new entry rather than an edit to an existing one.
_PROMPT_FILES = {
    "v1": "v1_note_analysis.md",
    "v2": "v2_note_analysis.md",
}


class UnknownPromptVersionError(ValueError):
    def __init__(self, version: str) -> None:
        super().__init__(f"Unknown prompt version '{version}'. Available: {sorted(_PROMPT_FILES)}.")


@lru_cache(maxsize=len(_PROMPT_FILES))
def load_prompt_template(version: str) -> str:
    filename = _PROMPT_FILES.get(version)
    if filename is None:
        raise UnknownPromptVersionError(version)

    template = (PROMPT_DIRECTORY / filename).read_text(encoding="utf-8")
    if NOTE_PLACEHOLDER not in template:
        raise ValueError(f"Prompt '{version}' is missing the {NOTE_PLACEHOLDER} placeholder.")
    return template


def render_prompt(version: str, note_content: str) -> str:
    """Insert the note into the template.

    `str.replace` rather than `str.format`: a note containing braces would make
    `format` raise, and clinical notes contain all sorts of punctuation.
    """
    return load_prompt_template(version).replace(NOTE_PLACEHOLDER, note_content)


def available_versions() -> list[str]:
    return sorted(_PROMPT_FILES)
