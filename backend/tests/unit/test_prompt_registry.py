"""The prompt convention is enforced, not just documented.

A prompt added later that omits its prohibitions or its output contract fails
here rather than in production.
"""

import pytest

from src.agent.prompts.registry import (
    NOTE_PLACEHOLDER,
    UnknownPromptVersionError,
    available_versions,
    load_prompt_template,
    render_prompt,
)

REQUIRED_SECTIONS = (
    "[ROLE & CONSTRAINTS]",
    "[INSTRUCTIONS]",
    "[DON'TS]",
    "[OUTPUT FORMAT]",
    "[EXAMPLES]",
)


@pytest.mark.parametrize("version", available_versions())
def test_every_prompt_declares_the_required_sections(version: str) -> None:
    template = load_prompt_template(version)

    missing = [section for section in REQUIRED_SECTIONS if section not in template]

    assert missing == [], f"Prompt {version} is missing sections: {missing}"


@pytest.mark.parametrize("version", available_versions())
def test_every_prompt_carries_the_note_placeholder(version: str) -> None:
    assert NOTE_PLACEHOLDER in load_prompt_template(version)


@pytest.mark.parametrize("version", available_versions())
def test_every_prompt_names_all_three_documentation_statuses(version: str) -> None:
    """The enum and the prompt must not drift apart."""
    template = load_prompt_template(version)

    for status in ("well_documented", "ambiguous", "mentioned_without_plan"):
        assert status in template


def test_rendering_substitutes_the_note() -> None:
    rendered = render_prompt("v1", "Patient reports chest pain.")

    assert "Patient reports chest pain." in rendered
    assert NOTE_PLACEHOLDER not in rendered


def test_rendering_tolerates_braces_in_the_note() -> None:
    """str.format would raise on a note containing braces; replace does not."""
    rendered = render_prompt("v1", "Dose {unclear} per chart.")

    assert "Dose {unclear} per chart." in rendered


def test_an_unknown_version_is_rejected() -> None:
    with pytest.raises(UnknownPromptVersionError):
        load_prompt_template("v99")
