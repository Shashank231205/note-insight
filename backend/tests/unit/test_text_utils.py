from src.utils.hashing import content_fingerprint
from src.utils.text import (
    build_normalization_offset_map,
    count_words,
    normalize_for_matching,
)


def test_word_count_ignores_surrounding_and_repeated_whitespace() -> None:
    assert count_words("  patient   reports  chest pain \n\n") == 4


def test_word_count_of_empty_text_is_zero() -> None:
    assert count_words("   \n\t ") == 0


def test_normalization_folds_typographic_quotes_and_case() -> None:
    assert normalize_for_matching("Patient’s “A1c”") == "patient's \"a1c\""


def test_normalization_collapses_internal_whitespace() -> None:
    assert normalize_for_matching("A1c\n\n  was   8.2") == "a1c was 8.2"


def test_offset_map_points_back_into_the_original_text() -> None:
    original = "Patient   reports\nchest pain."
    normalized, offsets = build_normalization_offset_map(original)

    assert normalized == "patient reports chest pain."
    index = normalized.index("chest")
    assert original[offsets[index] : offsets[index] + 5] == "chest"


def test_offset_map_has_one_entry_per_normalized_character() -> None:
    normalized, offsets = build_normalization_offset_map("  Multiple   spaces  here  ")

    assert len(normalized) == len(offsets)


def test_fingerprint_is_stable_across_reflowed_whitespace() -> None:
    assert content_fingerprint("chest pain\nfor two days") == content_fingerprint(
        "chest pain   for two days"
    )


def test_fingerprint_differs_for_different_content() -> None:
    assert content_fingerprint("chest pain") != content_fingerprint("back pain")
