"""Prepare the demo account a reviewer signs in with.

Creates one account, submits the three synthetic sample notes, analyses each,
and reviews one of them — so the history page, the AI-versus-human diff and the
inline evidence highlighting are all visible immediately, rather than after a
cold start plus a model call.

Run against the deployed API, not the database, so the seeded data goes through
the same validation, verification and persistence path as a real submission:

    python scripts/seed_demo.py --api https://your-api.onrender.com

Everything it writes is synthetic. It never touches real patient data because
none exists anywhere in this project.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

SAMPLE_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "docs" / "sample-notes"

# Firebase's web API key. Public by design: it identifies the project and
# authorises nothing. Sign-in still requires the password.
IDENTITY_TOOLKIT = "https://identitytoolkit.googleapis.com/v1/accounts"

SAMPLES = [
    ("01-diabetes-ambiguous.md", "PT-2041", "2026-02-18"),
    ("02-chf-well-documented.md", "PT-8830", "2026-02-19"),
    ("03-polypharmacy-gaps.md", "PT-1156", "2026-02-20"),
]


def read_note_body(filename: str) -> str:
    """Return the clinical text only.

    The sample files carry a markdown header describing what each note is for,
    including the findings it is expected to produce. Submitting that would feed
    the model the answer key and make the evidence numbers meaningless.
    """
    raw = (SAMPLE_DIRECTORY / filename).read_text(encoding="utf-8")
    body = raw.split("\n---\n", 1)[1] if "\n---\n" in raw else raw
    return re.sub(r"^\s*Pseudonym:.*\n\s*Visit date:.*\n", "", body).strip()


def sign_in(web_api_key: str, email: str, password: str) -> str:
    """Return an ID token, creating the account if it does not exist yet."""
    with httpx.Client(timeout=30) as client:
        created = client.post(
            f"{IDENTITY_TOOLKIT}:signUp?key={web_api_key}",
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        if created.status_code == 200:
            return str(created.json()["idToken"])

        existing = client.post(
            f"{IDENTITY_TOOLKIT}:signInWithPassword?key={web_api_key}",
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        existing.raise_for_status()
        return str(existing.json()["idToken"])


def review_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    """A realistic review: mostly accepted, one edited, one rejected, one added.

    The point of the demo is the diff, so the seeded review has to actually
    disagree with the model somewhere.
    """
    conditions = analysis["output"]["conditions"]
    reviewed: list[dict[str, Any]] = []

    for index, condition in enumerate(conditions):
        if index == 0:
            action = "edited"
        elif index == len(conditions) - 1:
            action = "rejected"
        else:
            action = "accepted"
        reviewed.append(
            {
                "condition_id": condition["condition_id"],
                "origin": "ai",
                "action": action,
                "name": (
                    "Type 2 diabetes mellitus, uncontrolled"
                    if action == "edited"
                    else condition["name"]
                ),
                "evidence_quote": condition["evidence_quote"],
                "documentation_status": condition["documentation_status"],
                "icd10_code": "E11.65" if action == "edited" else condition["icd10_code"],
                "rejection_reason": (
                    "Supported by symptoms only; no diagnosis stated in the note."
                    if action == "rejected"
                    else None
                ),
            }
        )

    reviewed.append(
        {
            "condition_id": "human-added-1",
            "origin": "human",
            "action": "added",
            "name": "Diabetic peripheral neuropathy",
            "evidence_quote": "Patient started on gabapentin 300 milligrams at bedtime.",
            "documentation_status": "mentioned_without_plan",
            "icd10_code": "E11.42",
            "rejection_reason": None,
        }
    )

    return {
        "reviewed_conditions": reviewed,
        "reviewed_gaps": [],
        "summary_override": None,
        "reviewer_note": (
            "Diabetes re-coded with type and control status. Neuropathy recorded as diabetic."
        ),
    }


def seed(api: str, web_api_key: str, email: str, password: str) -> None:
    token = sign_in(web_api_key, email, password)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"{api.rstrip('/')}/api/v1"

    with httpx.Client(timeout=180, headers=headers) as client:
        client.get(f"{base}/users/me").raise_for_status()
        print(f"signed in as {email}")

        for filename, pseudonym, visit_date in SAMPLES:
            note = client.post(
                f"{base}/notes",
                json={
                    "content": read_note_body(filename),
                    "pseudonym": pseudonym,
                    "visit_date": visit_date,
                },
            )
            note.raise_for_status()
            note_id = note.json()["note_id"]

            analysis = client.post(f"{base}/notes/{note_id}/analyses", json={"force": False})
            analysis.raise_for_status()
            body = analysis.json()
            verification = body["verification"]
            print(
                f"  {pseudonym}: {len(body['output']['conditions'])} conditions, "
                f"{verification['verified_count']} quotes verified, "
                f"{len(body['output']['documentation_gaps'])} gaps"
            )

            # Only the first note is reviewed. Leaving the others pending is
            # deliberate: the history page should show both states.
            if filename == SAMPLES[0][0]:
                review = client.post(
                    f"{base}/analyses/{body['analysis_id']}/reviews",
                    json=review_payload(body),
                )
                review.raise_for_status()
                print(f"  {pseudonym}: reviewed (version {review.json()['version']})")

            # The per-user limiter allows a short burst; pace the calls so
            # seeding never trips it.
            time.sleep(8)

    print("\nseeded. sign in with:")
    print(f"  {email}")
    print(f"  {password}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="Base URL of the deployed API")
    parser.add_argument("--web-api-key", required=True, help="Firebase web API key")
    parser.add_argument("--email", default="reviewer@note-insight.demo")
    parser.add_argument("--password", default="NoteInsight2026!")
    args = parser.parse_args()

    try:
        seed(args.api, args.web_api_key, args.email, args.password)
    except httpx.HTTPStatusError as error:
        print(f"failed: {error.response.status_code} {error.response.text[:300]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
