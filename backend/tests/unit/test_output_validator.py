"""What the system does when the model returns something we cannot use."""

import json

from src.agent.validators.output import OutputFailureCode, parse_analysis_output

VALID_PAYLOAD = {
    "summary": "Follow-up for two chronic conditions.",
    "conditions": [
        {
            "condition_name": "Type 2 diabetes mellitus",
            "evidence_quote": "A1c today is 8.4%",
            "documentation_status": "ambiguous",
            "icd10_code": "E11.9",
            "confidence": 0.82,
        }
    ],
    "documentation_gaps": [
        {
            "description": "Control status is not stated.",
            "related_condition_name": "Type 2 diabetes mellitus",
            "severity": "high",
        }
    ],
}


class TestWellFormedOutput:
    def test_plain_json_is_accepted(self) -> None:
        result = parse_analysis_output(json.dumps(VALID_PAYLOAD))

        assert result.succeeded
        assert result.analysis is not None
        assert result.analysis.conditions[0].condition_name == "Type 2 diabetes mellitus"

    def test_json_inside_a_markdown_fence_is_recovered(self) -> None:
        result = parse_analysis_output(f"```json\n{json.dumps(VALID_PAYLOAD)}\n```")

        assert result.succeeded

    def test_json_with_conversational_padding_is_recovered(self) -> None:
        wrapped = f"Certainly! Here is the analysis:\n{json.dumps(VALID_PAYLOAD)}\nLet me know."
        result = parse_analysis_output(wrapped)

        assert result.succeeded

    def test_an_analysis_with_no_conditions_is_valid(self) -> None:
        result = parse_analysis_output(
            json.dumps({"summary": "Nothing codeable.", "conditions": [], "documentation_gaps": []})
        )

        assert result.succeeded
        assert result.analysis is not None
        assert result.analysis.conditions == []


class TestMalformedOutput:
    def test_an_empty_response_is_reported_as_empty(self) -> None:
        result = parse_analysis_output("   ")

        assert not result.succeeded
        assert result.failure is not None
        assert result.failure.code is OutputFailureCode.EMPTY_RESPONSE

    def test_prose_with_no_json_is_reported_as_not_json(self) -> None:
        result = parse_analysis_output("The patient appears to have diabetes and hypertension.")

        assert result.failure is not None
        assert result.failure.code is OutputFailureCode.NOT_JSON

    def test_truncated_json_is_reported_as_not_json(self) -> None:
        result = parse_analysis_output('{"summary": "Follow-up", "conditions": [{"condition_')

        assert result.failure is not None
        assert result.failure.code is OutputFailureCode.NOT_JSON

    def test_a_missing_required_field_is_a_schema_mismatch(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        del payload["conditions"][0]["documentation_status"]

        result = parse_analysis_output(json.dumps(payload))

        assert result.failure is not None
        assert result.failure.code is OutputFailureCode.SCHEMA_MISMATCH

    def test_an_unknown_enum_value_is_a_schema_mismatch(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        payload["conditions"][0]["documentation_status"] = "perfectly_fine"

        result = parse_analysis_output(json.dumps(payload))

        assert result.failure is not None
        assert result.failure.code is OutputFailureCode.SCHEMA_MISMATCH

    def test_a_json_array_instead_of_an_object_is_rejected(self) -> None:
        result = parse_analysis_output('[{"summary": "wrong shape"}]')

        assert not result.succeeded

    def test_failure_keeps_a_bounded_excerpt_for_debugging(self) -> None:
        result = parse_analysis_output("x" * 5000)

        assert result.failure is not None
        assert result.failure.raw_excerpt is not None
        assert len(result.failure.raw_excerpt) <= 501


class TestLenientFieldHandling:
    def test_a_confidence_above_one_is_clamped_rather_than_rejected(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        payload["conditions"][0]["confidence"] = 1.4

        result = parse_analysis_output(json.dumps(payload))

        assert result.analysis is not None
        assert result.analysis.conditions[0].confidence == 1.0

    def test_a_negative_confidence_is_clamped(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        payload["conditions"][0]["confidence"] = -0.5

        result = parse_analysis_output(json.dumps(payload))

        assert result.analysis is not None
        assert result.analysis.conditions[0].confidence == 0.0

    def test_an_icd10_code_is_normalized(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        payload["conditions"][0]["icd10_code"] = "  e11.9  "

        result = parse_analysis_output(json.dumps(payload))

        assert result.analysis is not None
        assert result.analysis.conditions[0].icd10_code == "E11.9"

    def test_unexpected_extra_fields_are_ignored_not_fatal(self) -> None:
        payload = json.loads(json.dumps(VALID_PAYLOAD))
        payload["conditions"][0]["clinical_advice"] = "Start insulin."

        result = parse_analysis_output(json.dumps(payload))

        assert result.succeeded
