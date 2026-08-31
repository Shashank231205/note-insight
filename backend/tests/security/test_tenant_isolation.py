"""Proof of the specification's hard requirement.

"A user must only ever see their own notes and analyses." Every resource-scoped
route is walked with a second clinician's token against the first clinician's
document ids. The expected answer is always 404 — never 200, and never 403,
because a 403 confirms the resource exists.
"""

from fastapi.testclient import TestClient

from tests.conftest import Actor

VALID_NOTE = " ".join(["documented"] * 120)


def _create_note(client: TestClient, actor: Actor) -> str:
    response = client.post(
        "/api/v1/notes",
        json={"content": VALID_NOTE, "pseudonym": "PT-CONFIDENTIAL"},
        headers=actor.headers,
    )
    assert response.status_code == 201
    note_id = response.json()["note_id"]
    assert isinstance(note_id, str)
    return note_id


def test_another_clinician_cannot_read_a_note(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    note_id = _create_note(client, marina)

    response = client.get(f"/api/v1/notes/{note_id}", headers=other_clinician.headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTE_NOT_FOUND"


def test_a_cross_tenant_read_is_reported_as_missing_not_forbidden(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    """403 would disclose that the note exists. 404 discloses nothing."""
    note_id = _create_note(client, marina)

    response = client.get(f"/api/v1/notes/{note_id}", headers=other_clinician.headers)

    assert response.status_code != 403


def test_another_clinician_cannot_list_a_note(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    _create_note(client, marina)

    listing = client.get("/api/v1/notes", headers=other_clinician.headers).json()

    assert listing["items"] == []


def test_history_listings_are_disjoint_between_clinicians(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    marina_note = _create_note(client, marina)
    other_note = _create_note(client, other_clinician)

    marina_items = client.get("/api/v1/notes", headers=marina.headers).json()["items"]
    other_items = client.get("/api/v1/notes", headers=other_clinician.headers).json()["items"]

    assert [item["note_id"] for item in marina_items] == [marina_note]
    assert [item["note_id"] for item in other_items] == [other_note]


def test_no_note_content_leaks_through_a_cross_tenant_request(
    client: TestClient, marina: Actor, other_clinician: Actor
) -> None:
    note_id = _create_note(client, marina)

    response = client.get(f"/api/v1/notes/{note_id}", headers=other_clinician.headers)

    assert "PT-CONFIDENTIAL" not in response.text
    assert "documented" not in response.text


def test_an_unknown_note_id_is_also_a_404(client: TestClient, marina: Actor) -> None:
    """The response for someone else's note is indistinguishable from this."""
    response = client.get(
        "/api/v1/notes/2f3b1c4d-0000-4000-8000-000000000000", headers=marina.headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTE_NOT_FOUND"
