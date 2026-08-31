from fastapi.testclient import TestClient

from tests.conftest import Actor

WORD = "documented"


def note_of(word_count: int) -> str:
    return " ".join([WORD] * word_count)


VALID_NOTE = note_of(120)


def create_note(client: TestClient, actor: Actor, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"content": VALID_NOTE}
    payload.update(overrides)
    response = client.post("/api/v1/notes", json=payload, headers=actor.headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


class TestNoteCreation:
    def test_a_valid_note_is_persisted_with_derived_fields(
        self, client: TestClient, marina: Actor
    ) -> None:
        body = create_note(client, marina, pseudonym="PT-014", visit_date="2026-03-01")

        assert body["word_count"] == 120
        assert body["pseudonym"] == "PT-014"
        assert body["review_status"] == "pending"
        assert body["analysis_count"] == 0
        assert body["latest_analysis_id"] is None

    def test_owner_uid_cannot_be_supplied_by_the_client(
        self, client: TestClient, marina: Actor
    ) -> None:
        response = client.post(
            "/api/v1/notes",
            json={"content": VALID_NOTE, "owner_uid": "uid-alvarez"},
            headers=marina.headers,
        )

        assert response.status_code == 422

    def test_note_is_owned_by_the_authenticated_caller(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = create_note(client, marina)["note_id"]

        listing = client.get("/api/v1/notes", headers=marina.headers).json()

        assert [item["note_id"] for item in listing["items"]] == [note_id]


class TestNoteValidation:
    def test_a_note_below_the_minimum_word_count_is_rejected(
        self, client: TestClient, marina: Actor
    ) -> None:
        response = client.post(
            "/api/v1/notes", json={"content": note_of(99)}, headers=marina.headers
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_a_note_at_exactly_the_minimum_is_accepted(
        self, client: TestClient, marina: Actor
    ) -> None:
        response = client.post(
            "/api/v1/notes", json={"content": note_of(100)}, headers=marina.headers
        )

        assert response.status_code == 201

    def test_a_note_at_exactly_the_maximum_is_accepted(
        self, client: TestClient, marina: Actor
    ) -> None:
        response = client.post(
            "/api/v1/notes", json={"content": note_of(3000)}, headers=marina.headers
        )

        assert response.status_code == 201

    def test_a_five_thousand_word_note_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.post(
            "/api/v1/notes", json={"content": note_of(5000)}, headers=marina.headers
        )

        assert response.status_code == 422

    def test_an_empty_note_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.post("/api/v1/notes", json={"content": ""}, headers=marina.headers)

        assert response.status_code == 422

    def test_a_whitespace_only_note_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.post(
            "/api/v1/notes", json={"content": "   \n\t  "}, headers=marina.headers
        )

        assert response.status_code == 422

    def test_a_single_enormous_token_is_rejected_by_the_character_ceiling(
        self, client: TestClient, marina: Actor
    ) -> None:
        """A 40,001-character "word" would pass a word-count-only check."""
        response = client.post(
            "/api/v1/notes", json={"content": "x" * 40_001}, headers=marina.headers
        )

        assert response.status_code == 422

    def test_a_future_visit_date_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.post(
            "/api/v1/notes",
            json={"content": VALID_NOTE, "visit_date": "2099-01-01"},
            headers=marina.headers,
        )

        assert response.status_code == 422

    def test_an_overlong_pseudonym_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.post(
            "/api/v1/notes",
            json={"content": VALID_NOTE, "pseudonym": "P" * 65},
            headers=marina.headers,
        )

        assert response.status_code == 422


class TestNoteHistory:
    def test_history_is_newest_first(self, client: TestClient, marina: Actor) -> None:
        first = create_note(client, marina, pseudonym="PT-001")["note_id"]
        second = create_note(client, marina, pseudonym="PT-002")["note_id"]

        items = client.get("/api/v1/notes", headers=marina.headers).json()["items"]

        assert [item["note_id"] for item in items] == [second, first]

    def test_history_rows_exclude_the_note_body(self, client: TestClient, marina: Actor) -> None:
        create_note(client, marina)

        items = client.get("/api/v1/notes", headers=marina.headers).json()["items"]

        assert "content" not in items[0]

    def test_pagination_walks_every_note_exactly_once(
        self, client: TestClient, marina: Actor
    ) -> None:
        created = {str(create_note(client, marina)["note_id"]) for _ in range(5)}

        seen: list[str] = []
        cursor: str | None = None
        while True:
            url = f"/api/v1/notes?limit=2{f'&cursor={cursor}' if cursor else ''}"
            page = client.get(url, headers=marina.headers).json()
            seen.extend(str(item["note_id"]) for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break

        assert sorted(seen) == sorted(created)

    def test_an_empty_history_returns_an_empty_page(
        self, client: TestClient, marina: Actor
    ) -> None:
        body = client.get("/api/v1/notes", headers=marina.headers).json()

        assert body == {"items": [], "next_cursor": None}

    def test_a_malformed_cursor_is_a_client_error(self, client: TestClient, marina: Actor) -> None:
        response = client.get("/api/v1/notes?cursor=garbage", headers=marina.headers)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"

    def test_limit_above_the_ceiling_is_rejected(self, client: TestClient, marina: Actor) -> None:
        response = client.get("/api/v1/notes?limit=500", headers=marina.headers)

        assert response.status_code == 422
