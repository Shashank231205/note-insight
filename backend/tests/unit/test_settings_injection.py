"""An application must run entirely on the Settings it was constructed with.

Routes previously depended on the process-wide cached settings while the
middleware used the injected instance, so an app built for one configuration
could execute requests under another — which made the test suite depend on
whatever happened to be in the developer's .env file.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.settings import SETTINGS_STATE_KEY, get_request_settings
from src.core.config import Environment, LLMProviderName, Settings
from src.main import create_app


def _settings(api_version: str) -> Settings:
    return Settings(
        environment=Environment.TEST,
        api_version=api_version,
        llm_provider=LLMProviderName.MOCK,
        firebase_project_id="note-insight-test",
    )


def test_create_app_records_its_settings_on_state() -> None:
    settings = _settings("9.9.9")

    app = create_app(settings)

    assert getattr(app.state, SETTINGS_STATE_KEY) is settings


def test_routes_read_the_injected_settings_not_the_environment() -> None:
    app = create_app(_settings("9.9.9"))

    body = TestClient(app).get("/health").json()

    assert body["version"] == "9.9.9"


def test_two_apps_do_not_share_configuration() -> None:
    first = TestClient(create_app(_settings("1.1.1"))).get("/health").json()
    second = TestClient(create_app(_settings("2.2.2"))).get("/health").json()

    assert (first["version"], second["version"]) == ("1.1.1", "2.2.2")


def test_settings_fall_back_to_the_environment_when_state_is_unset() -> None:
    """A bare FastAPI app (no create_app) still resolves settings."""

    class _Request:
        app = FastAPI()

    assert isinstance(get_request_settings(_Request()), Settings)  # type: ignore[arg-type]
