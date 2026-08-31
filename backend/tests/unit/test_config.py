import pytest

from src.core.config import Environment, LLMProviderName, Settings


def test_wildcard_cors_origin_is_rejected() -> None:
    with pytest.raises(ValueError, match="explicit allowlist"):
        Settings(cors_allowed_origins="*")


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_allowed_origins="https://a.app , https://b.app")

    assert settings.cors_origin_list == ["https://a.app", "https://b.app"]


def test_gemini_provider_requires_at_least_one_key() -> None:
    settings = Settings(llm_provider=LLMProviderName.GEMINI, gemini_api_keys="")

    with pytest.raises(ValueError, match="GEMINI_API_KEYS"):
        settings.validate_runtime_readiness()


def test_gemini_keys_are_split_into_primary_and_fallbacks() -> None:
    settings = Settings(gemini_api_keys="primary, fallback ,")

    assert settings.gemini_key_list == ["primary", "fallback"]


def test_mock_provider_is_refused_in_production() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION,
        llm_provider=LLMProviderName.MOCK,
        firebase_project_id="p",
        firebase_service_account_json="{}",
    )

    with pytest.raises(ValueError, match="mock LLM provider"):
        settings.validate_runtime_readiness()


def test_word_bounds_must_be_coherent() -> None:
    settings = Settings(note_min_words=500, note_max_words=100)

    with pytest.raises(ValueError, match="NOTE_MIN_WORDS"):
        settings.validate_runtime_readiness()
