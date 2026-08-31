from fastapi.testclient import TestClient

from src.api.dependencies.services import RepositoryRegistry
from tests.conftest import Actor


def test_first_call_creates_the_profile_mirror(
    client: TestClient, marina: Actor, repositories: RepositoryRegistry
) -> None:
    response = client.get("/api/v1/users/me", headers=marina.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "uid-marina"
    assert body["email"] == "marina@clinic.test"


def test_profile_creation_is_idempotent(client: TestClient, marina: Actor) -> None:
    first = client.get("/api/v1/users/me", headers=marina.headers).json()
    second = client.get("/api/v1/users/me", headers=marina.headers).json()

    assert first["created_at"] == second["created_at"]


def test_each_caller_receives_only_their_own_profile(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    marina_profile = client.get("/api/v1/users/me", headers=marina.headers).json()
    other_profile = client.get("/api/v1/users/me", headers=other_clinician.headers).json()

    assert marina_profile["uid"] == "uid-marina"
    assert other_profile["uid"] == "uid-alvarez"


def test_response_does_not_leak_fields_outside_the_contract(
    client: TestClient, marina: Actor
) -> None:
    body = client.get("/api/v1/users/me", headers=marina.headers).json()

    assert set(body) == {"uid", "email", "display_name", "created_at"}
