from datetime import datetime

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    """Mirror of the Firebase identity.

    Credentials live in Firebase Auth and never touch Firestore. This document
    exists so the application can attribute notes and reviews without calling
    the Auth API on every request.
    """

    model_config = ConfigDict(frozen=True)

    uid: str
    email: str
    display_name: str | None
    created_at: datetime
    last_seen_at: datetime


class AuthenticatedUser(BaseModel):
    """The verified caller, built from a decoded Firebase ID token.

    Every value here comes from a signature-verified token. Nothing in this
    model is ever read from a request body.
    """

    model_config = ConfigDict(frozen=True)

    uid: str
    email: str
    email_verified: bool
