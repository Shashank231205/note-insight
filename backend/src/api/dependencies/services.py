"""Service construction.

Repositories and services are built here and injected into routes, so a route
never reaches for a Firestore client and a service never knows how it was
wired.
"""

from __future__ import annotations

from fastapi import Depends, Request
from google.cloud.firestore import Client as FirestoreClient

from src.core.config import Settings, get_settings
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
from src.services.auth.user_service import UserService
from src.services.notes.note_service import NoteService

REPOSITORIES_STATE_KEY = "repositories"


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
    request: Request, settings: Settings = Depends(get_settings)
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
