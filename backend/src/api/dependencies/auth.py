"""Authentication dependency.

Every route except /health depends on `get_current_user`. A test enumerates the
route table and asserts that, so a route added later cannot quietly be public.
"""

from __future__ import annotations

import asyncio

from fastapi import Depends, Header, Request

from src.api.dependencies.settings import get_request_settings
from src.core.config import Settings
from src.core.security import FirebaseTokenVerifier, TokenVerifier, extract_bearer_token
from src.models.user import AuthenticatedUser

VERIFIER_STATE_KEY = "token_verifier"


def get_token_verifier(
    request: Request,
    settings: Settings = Depends(get_request_settings),
) -> TokenVerifier:
    """Return the app's verifier, building the Firebase one on first use.

    Held on app state so tests can install a fake without patching modules.
    """
    existing = getattr(request.app.state, VERIFIER_STATE_KEY, None)
    if existing is not None:
        assert isinstance(existing, TokenVerifier)
        return existing

    verifier = FirebaseTokenVerifier(settings)
    setattr(request.app.state, VERIFIER_STATE_KEY, verifier)
    return verifier


async def get_current_user(
    authorization: str | None = Header(default=None),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    token = extract_bearer_token(authorization)
    # Verification can block on a public-key refresh, so it stays off the loop.
    return await asyncio.to_thread(verifier.verify, token)
