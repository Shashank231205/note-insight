"""Evidence verification.

Every quote the model attributes to the note is located in the note, or marked
as not found. This is the system's answer to "how do you know the model didn't
make this up?".

Three tiers, tried in order:

  exact       the quote appears verbatim in the note
  normalized  it appears once case, typographic punctuation and whitespace are
              folded — the common, benign case where a model tidies a quote
  fuzzy       the best-matching window of the note is similar enough to be the
              same passage with a small transcription slip

Below the fuzzy floor the quote is decomposed: if it can be covered by a
small number of long fragments that each appear in the note, it is `assembled`
— the model stitched real passages into a quote that does not exist as written.
That is reported separately from `not_found`, because "these words are in your
note but not together" and "these words are not in your note" are different
things for a clinician to act on. Neither counts as verified.

Anything else is `not_found`. Unverified conditions are
flagged and kept, never silently deleted: dropping them would destroy the
signal the human-review dataset exists to capture, and the clinician is the
right person to decide what a bad quote means.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher

from src.models.analysis import QuoteVerification, VerificationReport
from src.models.enums import QuoteVerificationStatus
from src.utils.text import build_normalization_offset_map, normalize_for_matching

# Below this similarity a match is not the same passage, it is a coincidence.
# Chosen conservatively: a false "not found" shows a warning the clinician can
# dismiss, while a false "verified" is the failure mode this module exists to
# prevent. Tuning it properly needs a corpus of real model output, which is
# recorded in the README as a known limitation.
FUZZY_MATCH_FLOOR = 0.85

# Quotes shorter than this are too small for fuzzy matching to be meaningful:
# almost any short string finds a plausible window in a long note.
MIN_FUZZY_QUOTE_LENGTH = 20

# Decomposition guards. Without them "assembled" would degenerate: any text can
# be built from short fragments of a long note, so a quote reachable only in
# many small pieces is a fabrication, not a stitched citation.
MIN_FRAGMENT_LENGTH = 12
MAX_FRAGMENTS = 4

# A gap this small between two fragments means the model was quoting one
# passage and dropped something out of the middle of it, not citing two
# passages. When what it dropped contains a number — a dose, a lab value — the
# quote asserts a finding the note does not, so it is a fabrication and not a
# stitched citation.
MAX_ELISION_GAP = 20

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class QuoteMatch:
    status: QuoteVerificationStatus
    score: float
    offset: int | None
    length: int | None


class EvidenceVerifier:
    """Locates model-supplied quotes inside the note the clinician wrote.

    Constructed per note so the normalization map is computed once rather than
    per quote.
    """

    def __init__(self, note_content: str) -> None:
        self._original = note_content
        self._normalized, self._offsets = build_normalization_offset_map(note_content)

    def verify_quote(self, quote: str) -> QuoteMatch:
        if not quote.strip():
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, 0.0, None, None)

        exact_offset = self._original.find(quote)
        if exact_offset != -1:
            return QuoteMatch(QuoteVerificationStatus.EXACT, 1.0, exact_offset, len(quote))

        normalized_quote = normalize_for_matching(quote)
        if not normalized_quote:
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, 0.0, None, None)

        normalized_offset = self._normalized.find(normalized_quote)
        if normalized_offset != -1:
            span = self._original_span(normalized_offset, len(normalized_quote))
            return QuoteMatch(QuoteVerificationStatus.NORMALIZED, 1.0, span[0], span[1])

        fuzzy = self._fuzzy_match(normalized_quote)
        if fuzzy.status is not QuoteVerificationStatus.NOT_FOUND:
            return fuzzy

        return self._assembled_match(normalized_quote, fallback=fuzzy)

    def _assembled_match(self, normalized_quote: str, fallback: QuoteMatch) -> QuoteMatch:
        """Decide whether the quote is real fragments joined, or invention.

        Greedily consumes the quote by taking, at each step, the longest prefix
        of what remains that occurs in the note. A quote covered by a few long
        fragments was assembled from the clinician's own words; one that needs
        many short fragments was not, because short strings match anything.
        """
        remaining = normalized_quote
        fragments: list[tuple[int, int]] = []

        while remaining:
            length = len(remaining)
            offset = -1
            while length >= MIN_FRAGMENT_LENGTH:
                offset = self._normalized.find(remaining[:length])
                if offset != -1:
                    break
                length -= 1

            if offset == -1 or length < MIN_FRAGMENT_LENGTH:
                return fallback

            fragments.append((offset, length))
            if len(fragments) > MAX_FRAGMENTS:
                return fallback
            remaining = remaining[length:].strip()

        if len(fragments) < 2:
            return fallback

        if self._elides_a_number(fragments):
            return fallback

        # Highlight the longest fragment: it is the largest span of the note the
        # model actually cited, so the clinician is shown real text rather than
        # nothing at all.
        #
        best_offset, best_length = max(fragments, key=lambda fragment: fragment[1])
        span = self._original_span(best_offset, best_length)
        covered = sum(length for _offset, length in fragments) / len(normalized_quote)
        return QuoteMatch(QuoteVerificationStatus.ASSEMBLED, round(covered, 4), span[0], span[1])

    def _fuzzy_match(self, normalized_quote: str) -> QuoteMatch:
        if len(normalized_quote) < MIN_FUZZY_QUOTE_LENGTH:
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, 0.0, None, None)

        matcher = SequenceMatcher(None, self._normalized, normalized_quote, autojunk=False)
        block = matcher.find_longest_match(0, len(self._normalized), 0, len(normalized_quote))
        if block.size == 0:
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, 0.0, None, None)

        # Compare the quote against the window of the note it best overlaps,
        # rather than against the whole note, so a short quote inside a long
        # note is not penalised for the note's length.
        window_start = max(0, block.a - block.b)
        window_end = min(len(self._normalized), window_start + len(normalized_quote))
        window = self._normalized[window_start:window_end]

        score = SequenceMatcher(None, window, normalized_quote, autojunk=False).ratio()
        if score < FUZZY_MATCH_FLOOR:
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, round(score, 4), None, None)

        # Character similarity treats "A1c 8.4%" and "A1c 6.1%" as a near match,
        # but in a clinical note the numbers are the substance: a changed lab
        # value is a fabricated finding, not a transcription slip. Fuzzy
        # matching is therefore not allowed to paper over a numeric difference.
        if _NUMBER.findall(window) != _NUMBER.findall(normalized_quote):
            return QuoteMatch(QuoteVerificationStatus.NOT_FOUND, round(score, 4), None, None)

        span = self._original_span(window_start, len(window))
        return QuoteMatch(QuoteVerificationStatus.FUZZY, round(score, 4), span[0], span[1])

    def _elides_a_number(self, fragments: list[tuple[int, int]]) -> bool:
        """True when the fragments skip a short run of text containing a number.

        Distinguishes "quoted one sentence but left out the dose" from "quoted
        two passages": the first leaves a small hole in otherwise continuous
        text, the second jumps between distant parts of the note.
        """
        ordered = sorted(fragments)
        pairs = zip(ordered, ordered[1:], strict=False)
        for (offset, length), (next_offset, _next_length) in pairs:
            gap = self._normalized[offset + length : next_offset]
            if 0 < len(gap) <= MAX_ELISION_GAP and _NUMBER.search(gap):
                return True
        return False

    def _original_span(self, normalized_start: int, normalized_length: int) -> tuple[int, int]:
        """Translate a span in normalized space back to the clinician's text.

        This is what lets the UI highlight the evidence inline in the note as
        it was actually written.
        """
        if not self._offsets or normalized_length <= 0:
            return (0, 0)

        start_index = min(normalized_start, len(self._offsets) - 1)
        end_index = min(normalized_start + normalized_length - 1, len(self._offsets) - 1)

        start = self._offsets[start_index]
        end = self._offsets[end_index] + 1
        return (start, max(0, end - start))


def build_verification_report(
    note_content: str, quotes_by_condition: dict[str, str]
) -> tuple[VerificationReport, dict[str, QuoteMatch]]:
    """Verify every condition's quote and summarise the outcome."""
    verifier = EvidenceVerifier(note_content)
    matches = {
        condition_id: verifier.verify_quote(quote)
        for condition_id, quote in quotes_by_condition.items()
    }

    results = [
        QuoteVerification(
            condition_id=condition_id,
            status=match.status,
            match_score=match.score,
            match_offset=match.offset,
            match_length=match.length,
        )
        for condition_id, match in matches.items()
    ]
    verified = sum(1 for result in results if result.is_verified)

    report = VerificationReport(
        checked_at=datetime.now(timezone.utc),
        quote_results=results,
        verified_count=verified,
        unverified_count=len(results) - verified,
    )
    return report, matches
