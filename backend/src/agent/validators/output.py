"""Parsing and validation of model output.

The model will occasionally return malformed or incomplete output. What this
module does about it is deliberate:

  1. Parse as JSON. If the text is wrapped in a markdown fence or has prose
     around it, recover the outermost JSON object — a structural repair, not a
     content one.
  2. Validate against RawAnalysis.
  3. If validation fails, fail. There is no second guess at what the model
     meant, and no regex extraction of fields from prose.

A repair that changed values would silently invent clinical content, which is
worse than an honest failure the clinician can retry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from pydantic import ValidationError

from src.agent.schemas.raw_output import RawAnalysis
from src.utils.text import truncate

RAW_EXCERPT_LIMIT = 500


class OutputFailureCode(str, Enum):
    EMPTY_RESPONSE = "empty_response"
    NOT_JSON = "not_json"
    TRUNCATED = "truncated"
    SCHEMA_MISMATCH = "schema_mismatch"


@dataclass(frozen=True)
class OutputFailure:
    code: OutputFailureCode
    message: str
    raw_excerpt: str | None


@dataclass(frozen=True)
class OutputParseResult:
    analysis: RawAnalysis | None
    failure: OutputFailure | None

    @property
    def succeeded(self) -> bool:
        return self.analysis is not None


def _looks_truncated(text: str) -> bool:
    """True when the text opens a JSON object that never closes.

    Distinguishes "the model wrote prose instead of JSON" from "the model was
    writing valid JSON and ran out of output budget". Both are unusable, but
    only the second is fixed by raising the token limit, so the failure record
    should not conflate them.
    """
    return text.lstrip().startswith(("{", "[")) and _recover_json_object(text) is None


def _recover_json_object(text: str) -> str | None:
    """Extract the outermost JSON object from a response with padding.

    Models sometimes wrap JSON in ```json fences or a sentence of preamble even
    when asked not to. Slicing between the first '{' and its matching '}' is a
    structural fix that cannot alter any value inside the object.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def parse_analysis_output(raw_text: str) -> OutputParseResult:
    if not raw_text.strip():
        return OutputParseResult(
            analysis=None,
            failure=OutputFailure(
                code=OutputFailureCode.EMPTY_RESPONSE,
                message="The model returned an empty response.",
                raw_excerpt=None,
            ),
        )

    candidate = raw_text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        recovered = _recover_json_object(candidate)
        if recovered is None:
            truncated = _looks_truncated(candidate)
            return OutputParseResult(
                analysis=None,
                failure=OutputFailure(
                    code=(OutputFailureCode.TRUNCATED if truncated else OutputFailureCode.NOT_JSON),
                    message=(
                        "The model response was cut off before the JSON object was complete."
                        if truncated
                        else "The model response did not contain a JSON object."
                    ),
                    raw_excerpt=truncate(candidate, RAW_EXCERPT_LIMIT),
                ),
            )
        try:
            payload = json.loads(recovered)
        except json.JSONDecodeError as exc:
            return OutputParseResult(
                analysis=None,
                failure=OutputFailure(
                    code=OutputFailureCode.NOT_JSON,
                    message=f"The model response was not valid JSON: {exc.msg}.",
                    raw_excerpt=truncate(candidate, RAW_EXCERPT_LIMIT),
                ),
            )

    try:
        analysis = RawAnalysis.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else None
        location = ".".join(str(part) for part in first["loc"]) if first else "response"
        detail = first["msg"] if first else "did not match the expected schema"
        return OutputParseResult(
            analysis=None,
            failure=OutputFailure(
                code=OutputFailureCode.SCHEMA_MISMATCH,
                message=f"The model response failed schema validation at {location}: {detail}.",
                raw_excerpt=truncate(candidate, RAW_EXCERPT_LIMIT),
            ),
        )

    return OutputParseResult(analysis=analysis, failure=None)
