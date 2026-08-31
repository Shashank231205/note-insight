"""Service construction.

Repositories and services are built here and injected into routes, so a route
never reaches for a Firestore client and a service never knows how it was
wired.
"""

from __future__ import annotations

from fastapi import Depends, Request
from google.cloud.firestore import Client as FirestoreClient

from src.agent.providers.base import LLMProvider
from src.agent.providers.mock import MockLLMProvider
from src.api.dependencies.settings import get_request_settings
from src.core.config import LLMProviderName, Settings
from src.core.firebase import get_firestore_client
from src.repositories.analysis_repository import FirestoreAnalysisRepository
from src.repositories.base import (
    AnalysisRepository,
    NoteRepository,
    ReviewRepository,
    UserRepository,
)
from src.repositories.note_repository import FirestoreNoteRepository
from src.repositories.review_repository import FirestoreReviewRepository
from src.repositories.user_repository import FirestoreUserRepository
from src.services.analysis.analysis_service import AnalysisService
from src.services.auth.user_service import UserService
from src.services.notes.note_service import NoteService
from src.services.review.review_service import ReviewService

REPOSITORIES_STATE_KEY = "repositories"
PROVIDER_STATE_KEY = "llm_provider"


class RepositoryRegistry:
    """The set of repositories the application runs against.

    Held on app state so tests can install in-memory implementations without
    patching modules or standing up an emulator.
    """

    def __init__(
        self,
        users: UserRepository,
        notes: NoteRepository,
        analyses: AnalysisRepository,
        reviews: ReviewRepository,
    ) -> None:
        self.users = users
        self.notes = notes
        self.analyses = analyses
        self.reviews = reviews

    @classmethod
    def from_firestore(cls, client: FirestoreClient) -> RepositoryRegistry:
        return cls(
            users=FirestoreUserRepository(client),
            notes=FirestoreNoteRepository(client),
            analyses=FirestoreAnalysisRepository(client),
            reviews=FirestoreReviewRepository(client),
        )


def get_repositories(
    request: Request, settings: Settings = Depends(get_request_settings)
) -> RepositoryRegistry:
    existing = getattr(request.app.state, REPOSITORIES_STATE_KEY, None)
    if isinstance(existing, RepositoryRegistry):
        return existing

    registry = RepositoryRegistry.from_firestore(get_firestore_client(settings))
    setattr(request.app.state, REPOSITORIES_STATE_KEY, registry)
    return registry


def get_user_service(
    repositories: RepositoryRegistry = Depends(get_repositories),
) -> UserService:
    return UserService(repositories.users)


def get_note_service(
    repositories: RepositoryRegistry = Depends(get_repositories),
) -> NoteService:
    return NoteService(repositories.notes)


def get_llm_provider(
    request: Request,
    settings: Settings = Depends(get_request_settings),
) -> LLMProvider:
    """Select the provider named in configuration.

    Held on app state so the instance (and its key pool) is shared across
    requests rather than rebuilt per call.
    """
    existing = getattr(request.app.state, PROVIDER_STATE_KEY, None)
    if isinstance(existing, LLMProvider):
        return existing

    provider: LLMProvider
    if settings.llm_provider is LLMProviderName.GEMINI:
        # Imported here rather than at module scope so a mock-provider run never
        # loads the Gemini SDK — tests and local development stay independent of
        # it, and an SDK import error surfaces only for the config that uses it.
        from src.agent.providers.gemini import GeminiProvider

        provider = GeminiProvider(settings)
    else:
        provider = MockLLMProvider()

    setattr(request.app.state, PROVIDER_STATE_KEY, provider)
    return provider


def get_analysis_service(
    settings: Settings = Depends(get_request_settings),
    repositories: RepositoryRegistry = Depends(get_repositories),
    provider: LLMProvider = Depends(get_llm_provider),
) -> AnalysisService:
    return AnalysisService(
        provider=provider,
        analyses=repositories.analyses,
        notes=repositories.notes,
        prompt_version=settings.prompt_version,
    )


def get_review_service(
    repositories: RepositoryRegistry = Depends(get_repositories),
) -> ReviewService:
    return ReviewService(
        reviews=repositories.reviews,
        analyses=repositories.analyses,
        notes=repositories.notes,
    )
