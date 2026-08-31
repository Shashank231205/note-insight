"""Tests for the hallucination guard.

The failure this module exists to prevent is a fabricated quote being marked
verified, so the "invented quote" cases are the important ones.
"""

from src.agent.validators.evidence import EvidenceVerifier, build_verification_report
from src.models.enums import QuoteVerificationStatus

NOTE = (
    "Patient returns for follow-up of type 2 diabetes mellitus. "
    "A1c today is 8.4%, up from 7.6% three months ago. "
    "Blood pressure 148/92, previously well controlled on lisinopril.\n\n"
    "Plan: increase metformin to 1000mg twice daily and recheck A1c in three months."
)


class TestQuoteFound:
    def test_a_verbatim_quote_is_exact(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote(
            "A1c today is 8.4%, up from 7.6% three months ago."
        )

        assert match.status is QuoteVerificationStatus.EXACT
        assert match.score == 1.0

    def test_an_exact_match_reports_the_offset_of_the_quote(self) -> None:
        quote = "Blood pressure 148/92"
        match = EvidenceVerifier(NOTE).verify_quote(quote)

        assert match.offset is not None
        assert NOTE[match.offset : match.offset + len(quote)] == quote

    def test_a_requoted_span_with_folded_punctuation_still_verifies(self) -> None:
        note = "Patient's A1c was 8.4% — up from 7.6%."
        match = EvidenceVerifier(note).verify_quote("Patient’s A1c was 8.4% — up from 7.6%.")

        assert match.status in {
            QuoteVerificationStatus.EXACT,
            QuoteVerificationStatus.NORMALIZED,
        }

    def test_a_quote_reflowed_across_lines_still_verifies(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote(
            "Plan: increase metformin to 1000mg\n   twice daily and recheck A1c in three months."
        )

        assert match.status is QuoteVerificationStatus.NORMALIZED

    def test_a_case_shifted_quote_still_verifies(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote("BLOOD PRESSURE 148/92")

        assert match.status is QuoteVerificationStatus.NORMALIZED

    def test_a_normalized_match_maps_back_into_the_original_text(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote("BLOOD PRESSURE 148/92")

        assert match.offset is not None and match.length is not None
        assert NOTE[match.offset : match.offset + match.length].lower().startswith("blood pressure")


class TestQuoteInvented:
    def test_a_fabricated_quote_is_not_found(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote(
            "Patient reports intermittent palpitations consistent with atrial fibrillation."
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND
        assert match.offset is None

    def test_a_quote_with_an_altered_lab_value_is_not_found(self) -> None:
        """The dangerous case: near-identical wording, fabricated number.

        Character similarity alone scores this ~0.88, above the fuzzy floor.
        A changed lab value is a different clinical fact, not a typo.
        """
        match = EvidenceVerifier(NOTE).verify_quote(
            "A1c today is 6.1%, down from 7.6% three months ago."
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_a_quote_with_an_altered_blood_pressure_is_not_found(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote(
            "Blood pressure 118/72, previously well controlled on lisinopril."
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_a_quote_with_a_dropped_number_is_not_found(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote(
            "Plan: increase metformin to twice daily and recheck A1c in three months."
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_an_empty_quote_is_not_found(self) -> None:
        match = EvidenceVerifier(NOTE).verify_quote("   ")

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_a_short_quote_is_not_fuzzy_matched(self) -> None:
        """Almost any short string finds a plausible window in a long note."""
        match = EvidenceVerifier(NOTE).verify_quote("cardiac")

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_verification_against_an_empty_note_finds_nothing(self) -> None:
        match = EvidenceVerifier("").verify_quote("anything at all in this quote")

        assert match.status is QuoteVerificationStatus.NOT_FOUND


class TestVerificationReport:
    def test_report_counts_verified_and_unverified_quotes(self) -> None:
        report, _ = build_verification_report(
            NOTE,
            {
                "c1": "Blood pressure 148/92",
                "c2": "Patient has a documented history of atrial fibrillation.",
            },
        )

        assert report.verified_count == 1
        assert report.unverified_count == 1

    def test_report_covers_every_condition_supplied(self) -> None:
        report, _ = build_verification_report(
            NOTE, {"c1": "A1c today is 8.4%", "c2": "invented", "c3": "lisinopril"}
        )

        assert {result.condition_id for result in report.quote_results} == {"c1", "c2", "c3"}

    def test_an_analysis_with_no_conditions_produces_an_empty_report(self) -> None:
        report, _ = build_verification_report(NOTE, {})

        assert report.quote_results == []
        assert report.verified_count == 0
        assert report.unverified_count == 0
