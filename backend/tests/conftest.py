from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.auth import VERIFIER_STATE_KEY
from src.api.dependencies.services import REPOSITORIES_STATE_KEY, RepositoryRegistry
from src.core.config import Environment, LLMProviderName, Settings
from src.main import create_app
from src.models.user import AuthenticatedUser
from tests.fakes import (
    FakeTokenVerifier,
    InMemoryAnalysisRepository,
    InMemoryNoteRepository,
    InMemoryReviewRepository,
    InMemoryUserRepository,
)


@dataclass
class Actor:
    """A signed-in user plus the header that authenticates them."""

    identity: AuthenticatedUser
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


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
def repositories() -> RepositoryRegistry:
    return RepositoryRegistry(
        users=InMemoryUserRepository(),
        notes=InMemoryNoteRepository(),
        analyses=InMemoryAnalysisRepository(),
        reviews=InMemoryReviewRepository(),
    )


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


@pytest.fixture
def app(
    settings: Settings,
    repositories: RepositoryRegistry,
    verifier: FakeTokenVerifier,
) -> FastAPI:
    application = create_app(settings)
    setattr(application.state, REPOSITORIES_STATE_KEY, repositories)
    setattr(application.state, VERIFIER_STATE_KEY, verifier)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def marina(verifier: FakeTokenVerifier) -> Actor:
    identity = verifier.register("token-marina", "uid-marina", "marina@clinic.test")
    return Actor(identity=identity, token="token-marina")


@pytest.fixture
def other_clinician(verifier: FakeTokenVerifier) -> Actor:
    """A second signed-in user, used to prove tenant isolation."""
    identity = verifier.register("token-alvarez", "uid-alvarez", "alvarez@clinic.test")
    return Actor(identity=identity, token="token-alvarez")
