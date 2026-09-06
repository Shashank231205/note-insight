"""End-to-end behaviour of the analysis endpoint, driven by the mock provider.

The mock's triggers make every failure path reproducible, so these assert what
the system actually does when the model misbehaves rather than hoping it does
something reasonable.
"""

from typing import Any

from fastapi.testclient import TestClient

from src.agent.providers.mock import (
    TRIGGER_EMPTY,
    TRIGGER_HALLUCINATE,
    TRIGGER_INCOMPLETE,
    TRIGGER_MALFORMED,
    TRIGGER_UNAVAILABLE,
)
from src.api.dependencies.services import RepositoryRegistry
from tests.conftest import Actor

CLINICAL_NOTE = (
    "Patient returns for follow-up of diabetes. A1c today is 8.4 percent. "
    "Blood pressure is elevated at 148/92 and hypertension remains on lisinopril. "
    "Kidney function is stable. "
) + " ".join(["Additional documented history follows."] * 20)


def submit_note(client: TestClient, actor: Actor, content: str = CLINICAL_NOTE) -> str:
    response = client.post("/api/v1/notes", json={"content": content}, headers=actor.headers)
    assert response.status_code == 201, response.text
    note_id = response.json()["note_id"]
    assert isinstance(note_id, str)
    return note_id


# Parsed JSON is genuinely dynamic; naming that is more honest than threading
# TypedDicts through assertions that only ever read one field.
JsonObject = dict[str, Any]


def analyze(client: TestClient, actor: Actor, note_id: str, force: bool = False) -> JsonObject:
    response = client.post(
        f"/api/v1/notes/{note_id}/analyses",
        json={"force": force},
        headers=actor.headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


class TestSuccessfulAnalysis:
    def test_analysis_returns_conditions_with_evidence_and_codes(
        self, client: TestClient, marina: Actor
    ) -> None:
        body = analyze(client, marina, submit_note(client, marina))

        assert body["status"] == "succeeded"
        output = body["output"]
        assert output is not None
        assert len(output["conditions"]) >= 2
        first = output["conditions"][0]
        assert set(first) == {
            "condition_id",
            "name",
            "evidence_quote",
            "documentation_status",
            "icd10_code",
            "confidence",
        }

    def test_every_quote_the_model_took_from_the_note_verifies(
        self, client: TestClient, marina: Actor
    ) -> None:
        body = analyze(client, marina, submit_note(client, marina))

        verification = body["verification"]
        assert verification is not None
        assert verification["unverified_count"] == 0

    def test_verification_offsets_point_into_the_note(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        body = analyze(client, marina, note_id)
        note = client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).json()

        for result in body["verification"]["quote_results"]:
            offset, length = result["match_offset"], result["match_length"]
            assert offset is not None
            assert note["content"][offset : offset + length].strip() != ""

    def test_the_note_records_the_analysis(self, client: TestClient, marina: Actor) -> None:
        note_id = submit_note(client, marina)
        body = analyze(client, marina, note_id)

        note = client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).json()

        assert note["latest_analysis_id"] == body["analysis_id"]
        assert note["analysis_count"] == 1
        assert note["condition_count"] == len(body["output"]["conditions"])

    def test_an_analysis_with_no_conditions_is_a_success_not_a_failure(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_EMPTY)

        body = analyze(client, marina, note_id)

        assert body["status"] == "succeeded"
        assert body["output"]["conditions"] == []


class TestModelMisbehaviour:
    def test_malformed_output_is_persisted_as_an_invalid_analysis(
        self, client: TestClient, marina: Actor
    ) -> None:
        """A 201: the model answered, we recorded that we could not trust it."""
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_MALFORMED)

        body = analyze(client, marina, note_id)

        assert body["status"] == "invalid_output"
        assert body["output"] is None
        assert body["failure"]["code"] == "not_json"

    def test_output_failing_the_schema_is_persisted_as_invalid(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_INCOMPLETE)

        body = analyze(client, marina, note_id)

        assert body["status"] == "invalid_output"
        assert body["failure"]["code"] == "schema_mismatch"

    def test_a_failed_analysis_is_still_retrievable_afterwards(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_MALFORMED)
        analysis_id = analyze(client, marina, note_id)["analysis_id"]

        response = client.get(f"/api/v1/analyses/{analysis_id}", headers=marina.headers)

        assert response.status_code == 200

    def test_the_raw_model_text_is_never_returned_to_the_client(
        self, client: TestClient, marina: Actor
    ) -> None:
        """The excerpt is kept for debugging but is unvalidated model output."""
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_MALFORMED)

        body = analyze(client, marina, note_id)

        assert set(body["failure"]) == {"code", "message"}

    def test_a_hallucinated_quote_is_flagged_and_kept(
        self, client: TestClient, marina: Actor
    ) -> None:
        """Dropping it would destroy the signal the review dataset exists for."""
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_HALLUCINATE)

        body = analyze(client, marina, note_id)

        assert body["verification"]["unverified_count"] == 1
        names = [condition["name"] for condition in body["output"]["conditions"]]
        assert "Atrial fibrillation" in names

    def test_an_unreachable_provider_is_a_503_not_a_500(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_UNAVAILABLE)

        response = client.post(
            f"/api/v1/notes/{note_id}/analyses", json={"force": False}, headers=marina.headers
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

    def test_the_note_survives_a_provider_outage(
        self, client: TestClient, marina: Actor, repositories: RepositoryRegistry
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_UNAVAILABLE)

        client.post(
            f"/api/v1/notes/{note_id}/analyses", json={"force": False}, headers=marina.headers
        )

        assert client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).status_code == 200

    def test_nothing_is_persisted_when_the_provider_is_unreachable(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina, CLINICAL_NOTE + TRIGGER_UNAVAILABLE)
        client.post(
            f"/api/v1/notes/{note_id}/analyses", json={"force": False}, headers=marina.headers
        )

        history = client.get(f"/api/v1/notes/{note_id}/analyses", headers=marina.headers).json()

        assert history == []


class TestReanalysisAndCaching:
    def test_an_identical_note_is_served_from_cache(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        first = analyze(client, marina, note_id)

        second = analyze(client, marina, note_id)

        assert second["analysis_id"] == first["analysis_id"]

    def test_force_bypasses_the_cache_and_creates_a_new_analysis(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        first = analyze(client, marina, note_id)

        second = analyze(client, marina, note_id, force=True)

        assert second["analysis_id"] != first["analysis_id"]

    def test_the_earlier_analysis_is_not_deleted_by_a_reanalysis(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        first = analyze(client, marina, note_id)
        second = analyze(client, marina, note_id, force=True)

        history = client.get(f"/api/v1/notes/{note_id}/analyses", headers=marina.headers).json()

        assert {item["analysis_id"] for item in history} == {
            first["analysis_id"],
            second["analysis_id"],
        }

    def test_the_note_points_at_the_newest_analysis(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        analyze(client, marina, note_id)
        second = analyze(client, marina, note_id, force=True)

        note = client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).json()

        assert note["latest_analysis_id"] == second["analysis_id"]


class TestAnalysisAccessControl:
    def test_another_clinician_cannot_analyze_a_note(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        note_id = submit_note(client, marina)

        response = client.post(
            f"/api/v1/notes/{note_id}/analyses",
            json={"force": False},
            headers=other_clinician.headers,
        )

        assert response.status_code == 404

    def test_another_clinician_cannot_read_an_analysis(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        analysis_id = analyze(client, marina, submit_note(client, marina))["analysis_id"]

        response = client.get(f"/api/v1/analyses/{analysis_id}", headers=other_clinician.headers)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"

    def test_another_clinician_cannot_list_a_notes_analyses(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        analyze(client, marina, note_id)

        response = client.get(f"/api/v1/notes/{note_id}/analyses", headers=other_clinician.headers)

        assert response.status_code == 404

    def test_a_cached_analysis_is_never_shared_across_clinicians(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        """Byte-identical notes must not cross the tenant boundary."""
        marina_analysis = analyze(client, marina, submit_note(client, marina))
        other_analysis = analyze(client, other_clinician, submit_note(client, other_clinician))

        assert marina_analysis["analysis_id"] != other_analysis["analysis_id"]


class TestRateLimiting:
    def test_sustained_analysis_requests_are_rate_limited(
        self, client: TestClient, marina: Actor
    ) -> None:
        statuses = []
        for index in range(6):
            note_id = submit_note(client, marina, CLINICAL_NOTE + f" Visit {index}.")
            response = client.post(
                f"/api/v1/notes/{note_id}/analyses", json={"force": False}, headers=marina.headers
            )
            statuses.append(response.status_code)

        assert 429 in statuses

    def test_a_rate_limited_response_tells_the_client_when_to_retry(
        self, client: TestClient, marina: Actor
    ) -> None:
        last_response = None
        for index in range(6):
            note_id = submit_note(client, marina, CLINICAL_NOTE + f" Encounter {index}.")
            last_response = client.post(
                f"/api/v1/notes/{note_id}/analyses", json={"force": False}, headers=marina.headers
            )
            if last_response.status_code == 429:
                break

        assert last_response is not None
        assert last_response.status_code == 429
        assert int(last_response.headers["Retry-After"]) > 0


class TestCacheReporting:
    """cache_hit describes the response, not the stored record.

    Persisted analyses always record False — that is how they were produced.
    A response served from an earlier identical run reports True, so the UI can
    say "reused an earlier analysis" instead of implying a fresh model call
    that never happened.
    """

    def test_a_repeat_analysis_reports_a_cache_hit(self, client: TestClient, marina: Actor) -> None:
        note_id = submit_note(client, marina)
        first = analyze(client, marina, note_id)

        second = analyze(client, marina, note_id)

        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert second["analysis_id"] == first["analysis_id"]

    def test_a_forced_analysis_is_never_a_cache_hit(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id = submit_note(client, marina)
        first = analyze(client, marina, note_id)

        forced = analyze(client, marina, note_id, force=True)

        assert forced["cache_hit"] is False
        assert forced["analysis_id"] != first["analysis_id"]


class TestCacheAcrossNotes:
    """A cache hit must never leave the note it was requested for unanalysed.

    The cache key is content, prompt version and model — deliberately not the
    note id, so submitting the same text twice does not pay twice. But the
    analysis that comes back has to belong to the note that asked for it.
    Returning the earlier note's document reports success while the new note
    still says "not analyzed", because nothing was ever linked to it.
    """

    def test_identical_text_on_a_second_note_gets_its_own_analysis(
        self, client: TestClient, marina: Actor
    ) -> None:
        first_note = submit_note(client, marina)
        first = analyze(client, marina, first_note)

        second_note = submit_note(client, marina)
        second = analyze(client, marina, second_note)

        assert second["note_id"] == second_note
        assert second["analysis_id"] != first["analysis_id"]
        assert second["cache_hit"] is True

    def test_the_second_note_reports_itself_as_analysed(
        self, client: TestClient, marina: Actor
    ) -> None:
        submit_note(client, marina)
        second_note = submit_note(client, marina)

        analyze(client, marina, second_note)

        note = client.get(f"/api/v1/notes/{second_note}", headers=marina.headers).json()
        assert note["analysis_count"] == 1
        assert note["latest_analysis_id"] is not None
        assert note["condition_count"] > 0

    def test_a_reused_analysis_is_listed_under_the_new_note(
        self, client: TestClient, marina: Actor
    ) -> None:
        submit_note(client, marina)
        second_note = submit_note(client, marina)
        analyze(client, marina, second_note)

        listed = client.get(f"/api/v1/notes/{second_note}/analyses", headers=marina.headers).json()

        assert len(listed) == 1
        assert listed[0]["note_id"] == second_note

    def test_reuse_does_not_bill_the_second_note_for_a_call_it_never_made(
        self, client: TestClient, marina: Actor
    ) -> None:
        """Zero latency because no call was made.

        The original analysis keeps the real cost, so summing usage across
        analyses still reports actual spend rather than double-counting one
        model call for every note that reused it.
        """
        submit_note(client, marina)
        second_note = submit_note(client, marina)

        second = analyze(client, marina, second_note)

        assert second["latency_ms"] == 0
