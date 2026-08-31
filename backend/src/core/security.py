"""Firebase ID token verification.

The token is verified with the Admin SDK, which checks signature, expiry,
audience and issuer against Google's published keys. We never decode a JWT by
hand, and we never read a user id from anywhere but the verified claims.

`TokenVerifier` is a protocol so the API layer can be tested without minting
real Firebase tokens.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from firebase_admin import auth as firebase_auth

from src.core.config import Settings
from src.core.errors import TokenExpiredError, TokenInvalidError
from src.core.firebase import initialize_firebase
from src.models.user import AuthenticatedUser


@runtime_checkable
class TokenVerifier(Protocol):
    def verify(self, id_token: str) -> AuthenticatedUser: ...


def _to_authenticated_user(claims: Mapping[str, object]) -> AuthenticatedUser:
    uid = claims.get("uid")
    email = claims.get("email")

    if not isinstance(uid, str) or not uid:
        raise TokenInvalidError("The authentication token is missing a subject.")
    if not isinstance(email, str) or not email:
        raise TokenInvalidError("The authentication token is missing an email address.")

    return AuthenticatedUser(
        uid=uid,
        email=email,
        email_verified=bool(claims.get("email_verified", False)),
    )


class FirebaseTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._app = initialize_firebase(settings)

    def verify(self, id_token: str) -> AuthenticatedUser:
        try:
            claims = firebase_auth.verify_id_token(
                id_token,
                app=self._app,
                check_revoked=True,
            )
        except firebase_auth.ExpiredIdTokenError as exc:
            raise TokenExpiredError from exc
        except firebase_auth.RevokedIdTokenError as exc:
            raise TokenExpiredError("This session has been revoked. Please sign in again.") from exc
        except (firebase_auth.InvalidIdTokenError, firebase_auth.UserDisabledError) as exc:
            raise TokenInvalidError from exc
        except ValueError as exc:
            raise TokenInvalidError from exc

        return _to_authenticated_user(claims)


def extract_bearer_token(authorization_header: str | None) -> str:
    """Pull the credential out of an Authorization header.

    A malformed header is a 401, never a 500.
    """
    if not authorization_header:
        raise TokenInvalidError("An Authorization header is required.")

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise TokenInvalidError("The Authorization header must be a Bearer token.")

    return token.strip()
