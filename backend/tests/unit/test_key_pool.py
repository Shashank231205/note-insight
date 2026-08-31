import pytest

from src.agent.providers.key_pool import GeminiKeyPool, NoKeysAvailableError


def test_a_pool_requires_at_least_one_key() -> None:
    with pytest.raises(ValueError, match="at least one key"):
        GeminiKeyPool([])


def test_the_primary_key_is_used_first() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])

    assert pool.acquire() == "primary"


def test_a_failed_key_is_skipped_on_the_next_acquire() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])
    pool.report_failure("primary")

    assert pool.acquire() == "fallback"


def test_a_retry_never_lands_on_the_key_that_just_failed() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])

    assert pool.acquire(exclude={"primary"}) == "fallback"


def test_exhausting_the_pool_raises_rather_than_returning_a_dead_key() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])
    pool.report_failure("primary")
    pool.report_failure("fallback")

    with pytest.raises(NoKeysAvailableError):
        pool.acquire()


def test_a_cooled_down_key_becomes_available_again() -> None:
    pool = GeminiKeyPool(["primary"], cooldown_seconds=0.0)
    pool.report_failure("primary")

    assert pool.acquire() == "primary"


def test_success_clears_a_previous_cooldown() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])
    pool.report_failure("primary")
    pool.report_success("primary")

    assert pool.acquire() == "primary"


def test_available_keys_excludes_cooling_keys() -> None:
    pool = GeminiKeyPool(["primary", "fallback"])
    pool.report_failure("primary")

    assert pool.available_keys() == ["fallback"]
