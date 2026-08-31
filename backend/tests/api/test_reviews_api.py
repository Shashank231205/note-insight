"""Human review: invariants, versioning, and the AI/human separation.

The guarantee under test throughout is that submitting a review never alters
the analysis, so "what did the model say, and what did the human change?"
remains answerable.
"""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import Actor

JsonObject = dict[str, Any]

CLINICAL_NOTE = (
    "Patient returns for follow-up of diabetes. A1c today is 8.4 percent. "
    "Blood pressure is elevated at 148/92 and hypertension remains on lisinopril. "
) + " ".join(["Additional documented history follows."] * 20)


def analyzed_note(client: TestClient, actor: Actor) -> tuple[str, JsonObject]:
    note = client.post(
        "/api/v1/notes", json={"content": CLINICAL_NOTE}, headers=actor.headers
    ).json()
    analysis = client.post(
        f"/api/v1/notes/{note['note_id']}/analyses",
        json={"force": False},
        headers=actor.headers,
    ).json()
    return str(note["note_id"]), analysis


def accepted_from(analysis: JsonObject) -> list[JsonObject]:
    """Reviewer accepts everything unchanged — the baseline submission."""
    return [
        {
            "condition_id": condition["condition_id"],
            "origin": "ai",
            "action": "accepted",
            "name": condition["name"],
            "evidence_quote": condition["evidence_quote"],
            "documentation_status": condition["documentation_status"],
            "icd10_code": condition["icd10_code"],
            "rejection_reason": None,
        }
        for condition in analysis["output"]["conditions"]
    ]


def submit(
    client: TestClient,
    actor: Actor,
    analysis_id: str,
    conditions: list[JsonObject],
    **extra: object,
) -> Any:
    payload: dict[str, object] = {"reviewed_conditions": conditions, "reviewed_gaps": []}
    payload.update(extra)
    return client.post(
        f"/api/v1/analyses/{analysis_id}/reviews", json=payload, headers=actor.headers
    )


class TestSubmittingAReview:
    def test_accepting_every_condition_creates_version_one(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)

        response = submit(client, marina, analysis["analysis_id"], accepted_from(analysis))

        assert response.status_code == 201
        assert response.json()["version"] == 1

    def test_the_note_is_marked_reviewed(self, client: TestClient, marina: Actor) -> None:
        note_id, analysis = analyzed_note(client, marina)
        review = submit(client, marina, analysis["analysis_id"], accepted_from(analysis)).json()

        note = client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).json()

        assert note["review_status"] == "reviewed"
        assert note["latest_review_id"] == review["review_id"]

    def test_an_edited_condition_records_the_human_value(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions[0]["action"] = "edited"
        conditions[0]["name"] = "Type 2 diabetes mellitus, uncontrolled"
        conditions[0]["documentation_status"] = "well_documented"

        review = submit(client, marina, analysis["analysis_id"], conditions).json()

        assert review["reviewed_conditions"][0]["name"] == "Type 2 diabetes mellitus, uncontrolled"
        assert review["reviewed_conditions"][0]["action"] == "edited"

    def test_a_clinician_can_add_a_condition_the_model_missed(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions.append(
            {
                "condition_id": "human-1",
                "origin": "human",
                "action": "added",
                "name": "Diabetic neuropathy",
                "evidence_quote": "",
                "documentation_status": "mentioned_without_plan",
                "icd10_code": "E11.40",
                "rejection_reason": None,
            }
        )

        review = submit(client, marina, analysis["analysis_id"], conditions).json()

        added = [item for item in review["reviewed_conditions"] if item["origin"] == "human"]
        assert len(added) == 1
        assert added[0]["name"] == "Diabetic neuropathy"

    def test_a_rejected_condition_is_excluded_from_the_note_count(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions[0]["action"] = "rejected"
        conditions[0]["rejection_reason"] = "This is family history, not an active condition."

        submit(client, marina, analysis["analysis_id"], conditions)

        note = client.get(f"/api/v1/notes/{note_id}", headers=marina.headers).json()

        assert note["condition_count"] == len(conditions) - 1


class TestTheAiOutputIsPreserved:
    def test_reviewing_does_not_alter_the_analysis(self, client: TestClient, marina: Actor) -> None:
        """The single most important guarantee in the product."""
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions[0]["name"] = "Something entirely different"
        conditions[0]["action"] = "edited"

        submit(client, marina, analysis["analysis_id"], conditions)

        reloaded = client.get(
            f"/api/v1/analyses/{analysis['analysis_id']}", headers=marina.headers
        ).json()

        assert reloaded["output"] == analysis["output"]

    def test_the_diff_between_model_and_human_is_recoverable(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        target_id = conditions[0]["condition_id"]
        conditions[0]["action"] = "edited"
        conditions[0]["name"] = "Corrected name"

        review = submit(client, marina, analysis["analysis_id"], conditions).json()

        ai_name = next(
            item["name"]
            for item in analysis["output"]["conditions"]
            if item["condition_id"] == target_id
        )
        human_name = next(
            item["name"]
            for item in review["reviewed_conditions"]
            if item["condition_id"] == target_id
        )

        assert ai_name != human_name

    def test_resubmitting_creates_a_new_version_and_keeps_the_old_one(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        first = submit(client, marina, analysis["analysis_id"], accepted_from(analysis)).json()
        second = submit(client, marina, analysis["analysis_id"], accepted_from(analysis)).json()

        history = client.get(
            f"/api/v1/analyses/{analysis['analysis_id']}/reviews", headers=marina.headers
        ).json()

        assert second["version"] == first["version"] + 1
        assert {item["review_id"] for item in history} == {
            first["review_id"],
            second["review_id"],
        }


class TestReviewInvariants:
    def test_a_condition_id_the_analysis_never_produced_is_rejected(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions[0]["condition_id"] = "not-from-this-analysis"

        response = submit(client, marina, analysis["analysis_id"], conditions)

        assert response.status_code == 400

    def test_a_human_condition_must_use_action_added(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions.append(
            {
                "condition_id": "human-1",
                "origin": "human",
                "action": "accepted",
                "name": "Added condition",
                "evidence_quote": "",
                "documentation_status": "ambiguous",
                "icd10_code": None,
                "rejection_reason": None,
            }
        )

        response = submit(client, marina, analysis["analysis_id"], conditions)

        assert response.status_code == 400

    def test_rejecting_without_a_reason_is_refused(self, client: TestClient, marina: Actor) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions[0]["action"] = "rejected"
        conditions[0]["rejection_reason"] = None

        response = submit(client, marina, analysis["analysis_id"], conditions)

        assert response.status_code == 400

    def test_a_duplicated_condition_is_refused(self, client: TestClient, marina: Actor) -> None:
        _, analysis = analyzed_note(client, marina)
        conditions = accepted_from(analysis)
        conditions.append(dict(conditions[0]))

        response = submit(client, marina, analysis["analysis_id"], conditions)

        assert response.status_code == 400

    def test_reviewing_a_stale_analysis_is_a_conflict(
        self, client: TestClient, marina: Actor
    ) -> None:
        note_id, analysis = analyzed_note(client, marina)
        client.post(
            f"/api/v1/notes/{note_id}/analyses", json={"force": True}, headers=marina.headers
        )

        response = submit(client, marina, analysis["analysis_id"], accepted_from(analysis))

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "REVIEW_CONFLICT"

    def test_an_unknown_analysis_cannot_be_reviewed(
        self, client: TestClient, marina: Actor
    ) -> None:
        response = submit(client, marina, "2f3b1c4d-0000-4000-8000-000000000000", [])

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"

    def test_owner_uid_cannot_be_supplied_in_the_payload(
        self, client: TestClient, marina: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)

        response = client.post(
            f"/api/v1/analyses/{analysis['analysis_id']}/reviews",
            json={
                "reviewed_conditions": accepted_from(analysis),
                "reviewed_gaps": [],
                "owner_uid": "uid-alvarez",
            },
            headers=marina.headers,
        )

        assert response.status_code == 422


class TestReviewAccessControl:
    def test_another_clinician_cannot_review_an_analysis(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        """404, not 409.

        A conflict would tell the caller the analysis exists and already has a
        review — the same disclosure a 403 would make.
        """
        _, analysis = analyzed_note(client, marina)

        response = submit(client, other_clinician, analysis["analysis_id"], accepted_from(analysis))

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"

    def test_another_clinician_cannot_read_reviews(
        self, client: TestClient, marina: Actor, other_clinician: Actor
    ) -> None:
        _, analysis = analyzed_note(client, marina)
        submit(client, marina, analysis["analysis_id"], accepted_from(analysis))

        response = client.get(
            f"/api/v1/analyses/{analysis['analysis_id']}/reviews",
            headers=other_clinician.headers,
        )

        assert response.json() == []
