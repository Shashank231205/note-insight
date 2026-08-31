"""Text normalization shared by the word counter and the evidence verifier.

Both need to agree on what a "word" is and on how to compare text that a model
may have reproduced with different whitespace or quote characters.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"\S+")

# Models routinely normalize typographic punctuation when quoting. Folding these
# to their ASCII equivalents is the difference between a quote that verifies and
# one that looks hallucinated.
_PUNCTUATION_FOLDING = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
        "…": "...",
    }
)


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def normalize_for_matching(text: str) -> str:
    """Casefold, fold typographic punctuation, and collapse whitespace.

    Used only for comparison. The original text is what gets stored and shown.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_PUNCTUATION_FOLDING)
    return collapse_whitespace(folded.casefold())


def build_normalization_offset_map(text: str) -> tuple[str, list[int]]:
    """Normalize text while recording where each output character came from.

    Returns the normalized string and a list mapping each normalized character
    index back to its index in the original text. This is what lets a match
    found in normalized space be highlighted in the text the clinician wrote.
    """
    normalized_chars: list[str] = []
    source_offsets: list[int] = []
    previous_was_space = True

    for index, raw_char in enumerate(text):
        folded = unicodedata.normalize("NFKC", raw_char).translate(_PUNCTUATION_FOLDING)
        for char in folded.casefold():
            if char.isspace():
                if previous_was_space:
                    continue
                normalized_chars.append(" ")
                source_offsets.append(index)
                previous_was_space = True
            else:
                normalized_chars.append(char)
                source_offsets.append(index)
                previous_was_space = False

    while normalized_chars and normalized_chars[-1] == " ":
        normalized_chars.pop()
        source_offsets.pop()

    return "".join(normalized_chars), source_offsets


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"
