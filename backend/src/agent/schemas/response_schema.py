"""The JSON schema handed to the model as a generation constraint.

Gemini supports a `responseSchema` that constrains decoding, which is what makes
the output structured rather than prose we would otherwise have to parse. It is
derived here from the same enums the domain uses, so a new documentation status
cannot be added in one place and forgotten in the other.

The schema is still not trusted: it constrains generation, it does not guarantee
it. Pydantic validation runs on the result regardless.
"""

from typing import Any

from src.models.enums import DocumentationStatus, GapSeverity


def build_analysis_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["summary", "conditions", "documentation_gaps"],
        "properties": {
            "summary": {
                "type": "string",
                "description": "Two or three sentences describing the encounter.",
            },
            "conditions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "condition_name",
                        "evidence_quote",
                        "documentation_status",
                        "confidence",
                    ],
                    "properties": {
                        "condition_name": {"type": "string"},
                        "evidence_quote": {
                            "type": "string",
                            "description": (
                                "A span copied character for character from the note. "
                                "Never paraphrased."
                            ),
                        },
                        "documentation_status": {
                            "type": "string",
                            "enum": [status.value for status in DocumentationStatus],
                        },
                        "icd10_code": {"type": "string", "nullable": True},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "documentation_gaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["description", "severity"],
                    "properties": {
                        "description": {"type": "string"},
                        "related_condition_name": {"type": "string", "nullable": True},
                        "severity": {
                            "type": "string",
                            "enum": [severity.value for severity in GapSeverity],
                        },
                    },
                },
            },
        },
    }
