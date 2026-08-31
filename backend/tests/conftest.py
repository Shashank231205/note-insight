import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import Environment, LLMProviderName, Settings
from src.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        log_level="WARNING",
        cors_allowed_origins="http://localhost:5173",
        llm_provider=LLMProviderName.MOCK,
        firebase_project_id="note-insight-test",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
