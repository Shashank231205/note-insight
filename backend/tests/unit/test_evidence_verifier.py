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


class TestAssembledQuotes:
    """A quote built from real fragments is not the same as an invented one.

    Observed against the live model on a medication-reconciliation note: to
    cite one drug it joined the list's opening words to a drug appearing later
    in the same sentence. Every word is the clinician's; the passage is not.
    Reporting that as "not found" tells the clinician the model may have
    invented a finding, which is the wrong thing to tell them.
    """

    NOTE = (
        "Subjective:\n\n"
        "Reports fatigue over the past two months. Sleep is fragmented, averaging "
        "five hours nightly.\n\n"
        "Current medication list reviewed: metformin 500 milligrams twice daily, "
        "levothyroxine 75 micrograms daily, sertraline 50 milligrams daily.\n\n"
        "Assessment and plan:\n\nDiscussed sleep hygiene. Patient will keep a sleep log."
    )

    def test_a_list_prefix_joined_to_a_later_item_is_assembled(self) -> None:
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Current medication list reviewed: levothyroxine 75 micrograms daily"
        )

        assert match.status is QuoteVerificationStatus.ASSEMBLED

    def test_passages_from_different_sections_are_assembled(self) -> None:
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Sleep is fragmented, averaging five hours nightly. Discussed sleep hygiene."
        )

        assert match.status is QuoteVerificationStatus.ASSEMBLED

    def test_an_assembled_quote_does_not_count_as_verified(self) -> None:
        report, _matches = build_verification_report(
            self.NOTE,
            {"c1": "Current medication list reviewed: levothyroxine 75 micrograms daily"},
        )

        assert report.verified_count == 0
        assert report.unverified_count == 1

    def test_an_assembled_quote_still_points_at_real_text(self) -> None:
        """The longest genuine fragment is offered for highlighting.

        Showing the clinician the largest span the model actually cited beats
        showing them nothing.
        """
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Current medication list reviewed: levothyroxine 75 micrograms daily"
        )

        assert match.offset is not None and match.length is not None
        assert self.NOTE[match.offset : match.offset + match.length] in self.NOTE

    def test_a_real_prefix_with_an_invented_tail_is_not_found(self) -> None:
        """The guard that makes this worth having.

        If a real opening could carry an invented ending into "assembled", the
        status would launder fabrications instead of catching them.
        """
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Current medication list reviewed: warfarin 10 milligrams nightly"
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_wholly_invented_text_is_not_found(self) -> None:
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Patient reports crushing chest pain radiating to the jaw since Tuesday"
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_a_genuinely_contiguous_quote_is_still_exact(self) -> None:
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote(
            "Current medication list reviewed: metformin 500 milligrams twice daily"
        )

        assert match.status is QuoteVerificationStatus.EXACT

    def test_text_reachable_only_in_many_small_pieces_is_not_found(self) -> None:
        """Any string can be built from short fragments of a long note."""
        verifier = EvidenceVerifier(self.NOTE)

        match = verifier.verify_quote("the past two log daily Reports plan will keep")

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_a_dropped_dose_is_not_excused_as_assembly(self) -> None:
        """The line between stitching and altering.

        Two real fragments separated by a short gap containing a number mean
        the model quoted one passage and left the dose out of the middle of it.
        The resulting quote asserts a plan the note does not, so it is a
        fabrication — not a citation of two passages.
        """
        note = "Plan: increase metformin to 1000mg twice daily and recheck A1c in three months."

        match = EvidenceVerifier(note).verify_quote(
            "Plan: increase metformin to twice daily and recheck A1c in three months."
        )

        assert match.status is QuoteVerificationStatus.NOT_FOUND

    def test_skipping_a_whole_list_item_is_still_assembly(self) -> None:
        """Contrast with the case above: a large jump is citation, not elision."""
        note = (
            "Current medication list reviewed: metformin 500 milligrams twice daily, "
            "levothyroxine 75 micrograms daily, sertraline 50 milligrams daily."
        )

        match = EvidenceVerifier(note).verify_quote(
            "Current medication list reviewed: sertraline 50 milligrams daily."
        )

        assert match.status is QuoteVerificationStatus.ASSEMBLED
