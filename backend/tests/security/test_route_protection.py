"""Structural guarantee that authentication cannot be forgotten.

Rather than testing the routes that exist today, this walks the application's
route table. A route added next month without the dependency fails here.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api.dependencies.auth import get_current_user

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/docs/oauth2-redirect"}


def _application_routes(app: FastAPI) -> list[APIRoute]:
    return [route for route in app.routes if isinstance(route, APIRoute)]


def test_every_route_except_the_public_allowlist_requires_authentication(app: FastAPI) -> None:
    unprotected: list[str] = []

    for route in _application_routes(app):
        if route.path in PUBLIC_PATHS:
            continue
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies if dependency.call
        }
        if get_current_user not in dependency_calls:
            unprotected.append(f"{sorted(route.methods)} {route.path}")

    assert unprotected == [], f"Routes missing authentication: {unprotected}"


def test_the_public_allowlist_contains_only_health_and_docs(app: FastAPI) -> None:
    """Guards the allowlist itself, so widening it is a deliberate edit."""
    declared_paths = {route.path for route in _application_routes(app)}

    assert declared_paths & PUBLIC_PATHS == {"/health"}


def test_protected_route_rejects_a_missing_authorization_header(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_protected_route_rejects_a_malformed_authorization_header(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "token-marina"})

    assert response.status_code == 401


def test_protected_route_rejects_an_unknown_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer forged"})

    assert response.status_code == 401


def test_empty_bearer_credential_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer "})

    assert response.status_code == 401
