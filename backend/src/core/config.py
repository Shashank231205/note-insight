from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class LLMProviderName(str, Enum):
    MOCK = "mock"
    GEMINI = "gemini"


class Settings(BaseSettings):
    """Typed application configuration.

    Constructed once at startup and injected everywhere. Missing or malformed
    values fail here rather than surfacing as an AttributeError mid-request.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    api_version: str = "1.0.0"

    cors_allowed_origins: str = "http://localhost:5173"

    firebase_project_id: str = ""
    firebase_service_account_json: str = ""
    firestore_emulator_host: str = ""
    firebase_auth_emulator_host: str = ""

    llm_provider: LLMProviderName = LLMProviderName.MOCK
    gemini_api_keys: str = ""
    gemini_model_id: str = "gemini-2.5-flash"
    llm_timeout_seconds: float = 45.0
    llm_max_output_tokens: int = 4096
    prompt_version: str = "v1"

    analysis_rate_limit_per_hour: int = 10
    analysis_rate_limit_burst: int = 3

    note_min_words: int = Field(default=100, ge=1)
    note_max_words: int = Field(default=3000, ge=1)
    note_max_chars: int = Field(default=40_000, ge=1)
    max_request_body_bytes: int = Field(default=262_144, ge=1024)

    @field_validator("cors_allowed_origins")
    @classmethod
    def reject_wildcard_origin(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("CORS_ALLOWED_ORIGINS must be an explicit allowlist, never '*'.")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def gemini_key_list(self) -> list[str]:
        return [key.strip() for key in self.gemini_api_keys.split(",") if key.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def validate_runtime_readiness(self) -> None:
        """Assert cross-field invariants that only matter once the app serves traffic."""
        if self.note_min_words > self.note_max_words:
            raise ValueError("NOTE_MIN_WORDS cannot exceed NOTE_MAX_WORDS.")

        if self.llm_provider is LLMProviderName.GEMINI and not self.gemini_key_list:
            raise ValueError("LLM_PROVIDER=gemini requires at least one key in GEMINI_API_KEYS.")

        if self.is_production:
            if not self.firebase_project_id:
                raise ValueError("FIREBASE_PROJECT_ID is required in production.")
            if not self.firebase_service_account_json:
                raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON is required in production.")
            if self.llm_provider is LLMProviderName.MOCK:
                raise ValueError("The mock LLM provider must not be used in production.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
