# Note Insight — Manual Test Cases

Real-world scenarios a reviewer can execute against a running instance. Each one states what a
person actually does, what should happen, and what was observed when it was run.

The automated suite (`cd backend && pytest`, 158 tests) covers the same failure paths without a
network. This document is for verifying the product as a human uses it.

**Status legend:** ✅ verified against live Firebase + Gemini · ⬜ not yet run

**Environment used for the recorded results:** backend on `localhost:8000`, frontend on
`localhost:5173`, `LLM_PROVIDER=gemini`, `gemini-2.5-flash`, prompt `v2`, Firebase project
`note-insight-e0a3d`.

---

## TC-01 — A new clinician signs up and reaches an empty workspace ✅

**Story.** Dr. Ríos has been given the URL and has no account.

**Steps**
1. Open the app URL with no session.
2. Observe where you land.
3. Choose sign-up, enter `marina@clinic.test` and a password of at least 6 characters.
4. Submit.

**Expected**
- Step 2 shows the login screen, not the app.
- After sign-up you are signed in and land on the note form.
- History is empty and says so in words, rather than showing a blank panel.
- The account appears in Firebase console → Authentication → Users.
- A document appears in the Firestore `users` collection keyed by the Firebase UID.

**Observed.** As expected. The `users` document is created by a fire-and-forget `GET /users/me`
on auth state change — this was a defect found during testing (the call existed but was never
made) and is now fixed.

---

## TC-02 — Submitting a real note and reading the analysis ✅

**Story.** Marina has just finished a visit and pastes the note before the patient leaves.

**Steps**
1. Sign in. Open the note form.
2. Pseudonym `PT-2041`, visit date `2026-02-18`.
3. Paste the body of `docs/sample-notes/01-diabetes-ambiguous.md`, from `Subjective:` down.
4. Submit and watch the screen while it works.

**Expected**
- A live word count while typing; submit stays enabled at ~300 words.
- A visible loading state during the call — never a frozen page.
- Analysis returns in under 10 seconds.
- Conditions listed with name, quoted evidence, documentation status, ICD-10 code, confidence.
- Diabetes and CKD are `ambiguous` — the note names neither the diabetes type/control status nor
  the CKD stage.
- Documentation gaps say specifically what to add.

**Observed.** 6 conditions in 5.9 s (2,700 tokens). Diabetes `ambiguous` E11.9, CKD `ambiguous`
N18.3, hypertension `well_documented` I10, hyperlipidemia `mentioned_without_plan` E78.5,
peripheral neuropathy `mentioned_without_plan` G62.9, obesity `mentioned_without_plan` E66.9.
Five gaps, including *"Diabetes is documented without type or control status."*

---

## TC-03 — The model invents a quote and the system notices ✅

**Story.** The single most important behaviour in the product. Instructions are not enforcement,
so the claim "this quote is from your note" has to be checked rather than trusted.

**Steps**
1. Analyse `01-diabetes-ambiguous.md` (TC-02).
2. Inspect each condition's evidence badge.
3. For any condition marked unverified, search the note text for the quoted string.

**Expected**
- Verified quotes are highlighted inline in the note body below.
- Any quote not found in the note is flagged with a visible warning.
- **The flagged condition is still shown, not silently deleted.**

**Observed — this fired for real.** On the v1 prompt, Gemini returned as one verbatim quote:

> "Notes occasional tingling in both feet… Foot examination shows diminished sensation to
> monofilament testing… Patient started on gabapentin 300 milligrams at bedtime."

Every sentence exists — at characters 562, 1510 and 1962, in three different sections. The
contiguous quote does not exist. The verifier reported `not_found` at similarity 0.59 and the
condition was kept and flagged. Prompt v2 now bans assembled quotes explicitly; verification went
from 2/6 to 13/13 across all three sample notes.

**Regression check.** Re-run this case after any prompt change. A drop in the verified count is
the signal that the prompt has regressed.

---

## TC-04 — Correcting the machine: edit, reject, and add ✅

**Story.** Marina disagrees with the draft. The machine is a draft, not an authority.

**Steps**
1. Open an analysed note.
2. **Edit** — rename "Diabetes mellitus" to "Type 2 diabetes mellitus, uncontrolled", change the
   code to `E11.65`.
3. **Reject** peripheral neuropathy, giving a reason.
4. **Add** a condition the model missed: "Diabetic peripheral neuropathy", `E11.42`.
5. Submit the review.

**Expected**
- Every field is editable.
- Rejection requires or accepts a reason.
- A manually added condition is marked as human-originated, not attributed to the model.
- After submission the page shows **what the model said beside what the human changed**.
- The analysis document is unchanged — corrections do not overwrite it.

**Observed.** Review `v1` created with six AI-origin conditions (one `edited`, one `rejected`,
four `accepted`) and one `human`-origin `added` condition. The analysis was untouched; both
versions are readable afterwards. The note's `review_status` flipped to `reviewed` and
`condition_count` updated in the same write.

---

## TC-05 — History survives signing out ✅

**Story.** Marina comes back the next morning.

**Steps**
1. After TC-04, sign out.
2. Sign back in.
3. Open History.
4. Click the reviewed note.

**Expected**
- Notes listed newest first with date, pseudonym, condition count and review status.
- The reviewed note shows `reviewed`; an unreviewed one shows `pending`.
- Opening it restores the full analysis **and** the corrections.

**Observed.** Correct ordering and statuses; corrections intact. The list renders from a single
owner-scoped query using the composite index — no per-row fan-out reads.

---

## TC-06 — One clinician cannot reach another's data ✅

**Story.** The brief's hard requirement: *"treat it as if real patient data were behind it."*

**Steps**
1. As user A, note the `note_id` and `analysis_id` from the URL and network tab.
2. Sign up as user B in a private window (`intruder@clinic.test`).
3. Confirm B's history is empty.
4. Paste A's note URL directly into B's browser.
5. With B's token, call each API route using A's ids:
   `GET /notes/{id}`, `GET /notes/{id}/analyses`, `GET /analyses/{id}`,
   `POST /notes/{id}/analyses`, `POST /analyses/{id}/reviews`, `GET /analyses/{id}/reviews`.

**Expected**
- B's history is empty.
- Every route returns **404** — never 200, and never 403, because a 403 confirms the resource
  exists.

**Observed.** Read routes and the analysis POST all 404. Review listing returns `200` with `[]` —
the query is owner-scoped so nothing leaks, but it is inconsistent with its siblings and is
recorded as a known limitation.

**A defect this case found.** `POST /analyses/{id}/reviews` originally returned **409
REVIEW_CONFLICT**, which told the intruder the analysis existed *and* had already been reviewed.
Now 404 `ANALYSIS_NOT_FOUND`, with two regression tests.

---

## TC-07 — Unauthenticated access is refused everywhere ✅

**Steps**
1. With no session, open `/`, `/history`, and a known note URL.
2. With no `Authorization` header, call `GET /api/v1/notes`, `/users/me`, `/notes/{id}`.
3. Repeat with `Authorization: Bearer not-a-token`.

**Expected**
- Every browser route shows the login screen.
- Every API route returns 401. The backend verifies the token — it never trusts a user id from
  the client.

**Observed.** All browser routes redirect to login. All API routes 401, including with a
malformed token. A payload containing `owner_uid` is ignored; there is a test asserting it.

---

## TC-08 — A session that expires mid-work ✅

**Story.** Marina leaves the tab open over lunch.

**Steps**
1. Sign in and leave the app idle for over an hour.
2. Submit a note or open History.

**Expected**
- The expired token is detected, refreshed silently, and the request retried once.
- Only if the refresh fails does the user land back on login — with an explanation, not a blank
  screen.

**Observed.** Directly at the API, an expired token returns
`401 {"code":"TOKEN_EXPIRED","message":"The session has expired. Please sign in again."}` — a
distinct code from a malformed token, which is what lets the client decide between refreshing and
giving up.

---

## TC-09 — Notes that are too short, too long, or empty ✅

**Steps**
1. Submit with the textarea empty.
2. Submit a single sentence (~11 words).
3. Paste a 5,000-word note.
4. Submit whitespace only.

**Expected**
- Submit is disabled client-side before the request, with the live count shown against the range.
- Server-side, each is a 422 that names the actual count and the permitted range — the client
  check is convenience, the server check is the rule.

**Observed**

| Input | Response |
|---|---|
| Empty | 422 — `content: String should have at least 1 character` |
| 11 words | 422 — `The note is 11 words long; it must be between 100 and 3000 words.` |
| 5,000 words | 422 — `The note is 5000 words long; it must be between 100 and 3000 words.` |
| Whitespace only | 422 |
| 200 KB body | **413**, rejected by middleware before parsing |

---

## TC-10 — The same note analysed twice ✅

**Story.** Marina clicks analyse again, unsure whether the first click registered.

**Steps**
1. Analyse a note.
2. Analyse the same note again without changing it.
3. Compare `analysis_id`, `cache_hit` and latency.

**Expected**
- No second Gemini call and no second charge.
- The same analysis is returned, and the response says it came from cache.

**Observed.** Identical `analysis_id`, `cache_hit: true`, no provider call in the logs. The cache
key is `(owner_uid, content_hash, prompt_version, model_id)`.

**A defect this case found.** `cache_hit` was persisted as `false` at creation and never updated,
so it could never be `true` — the UI could not distinguish a reused analysis from a fresh model
call. It now describes the response while the stored record keeps describing how it was produced.

---

## TC-11 — Re-analysing after a prompt improvement ✅

**Story.** The brief asks this directly: *"What happens when the same note is analyzed twice —
for example after you improve your prompt. Does the old analysis disappear? Should it?"*

**Steps**
1. Analyse a note under prompt `v1`.
2. Change `PROMPT_VERSION` to `v2` and restart.
3. Analyse the same note again.
4. List all analyses for that note.

**Expected**
- A **new** analysis document. The old one is not overwritten.
- Each records the `prompt_version`, `model_id` and `provider` that produced it, so historical
  rows stay interpretable.
- The version change alone busts the cache — the same note under a new prompt is a new question.

**Observed.** Three analyses retained on one note: `v1` at 2/6 verified, `v1` at 6/6, `v2` at
6/6. Nothing was destroyed.

**A defect this case found.** The prompt was initially edited *without* a version bump, which
would have served stale cached analyses under a changed prompt. `v1` is now preserved and
registered, and the change ships as `v2`.

---

## TC-12 — The model returns something unusable ⬜

**Story.** It will happen in production. What the system does about it has to be deliberate.

**How to force it.** Set `LLM_PROVIDER=mock`; the mock provider has fixtures for each case.

**Steps**
1. Trigger each fixture: prose instead of JSON, JSON of the wrong shape, output cut off
   mid-object, an empty response.
2. Inspect the persisted analysis and the UI.

**Expected**
- The failure is **persisted**, not swallowed — status `invalid_output` with a failure code and a
  truncated raw excerpt for debugging.
- The four codes are distinguished: `not_json`, `schema_mismatch`, `truncated`, `empty_response`.
- The note itself is untouched and can be retried.
- The UI says the analysis failed and offers a retry; it never shows a half-parsed result.
- **No value is ever recovered by regex.** Structural repair only — unwrapping a markdown fence
  cannot alter a value inside.

**Covered automatically** by `tests/unit/test_output_validator.py`.

**Seen live.** `truncated` fired on the first real Gemini call: thinking tokens consumed the
output budget and the JSON stopped mid-string. The validator rejected it correctly. That failure
is also what motivated splitting `truncated` from `not_json` — only one of them is fixed by
raising the token limit.

---

## TC-13 — Gemini is unreachable ✅

**Story.** Quota exhausted, network down, or the API is having a bad day.

**How to force it.** Disconnect the network, or set `GEMINI_API_KEYS` to two invalid keys.

**Steps**
1. Submit a note successfully.
2. Break connectivity.
3. Request the analysis.
4. Restore connectivity and retry.

**Expected**
- **503, not 500** — the request was well-formed and will likely succeed later.
- The note is already saved; nothing the clinician typed is lost.
- The UI offers a retry rather than an error page.
- Quota/auth failures (401/403/429) rotate to the fallback key and retry; the failed key cools
  down for 5 minutes. A dropped connection does **not** burn a key.

**Observed.** A TLS failure initially escaped as an unhandled **500** — a genuine defect, since a
network blip then read as an application bug. Transport errors are now caught in the provider and
mapped to `ProviderUnavailableError` → 503, with regression tests for connect errors, read
timeouts, TLS errors and timeouts, plus one asserting the key pool is not burned.

---

## TC-14 — Rate limiting a single user ⬜

**Story.** A script, a stuck retry loop, or an impatient double-click should not spend the day's
quota.

**Steps**
1. Request analyses in a tight loop as one user.
2. Continue past the burst allowance.

**Expected**
- The first few succeed (burst 3), then **429**.
- The response says when to retry.
- The limit is per user, not global — a second user is unaffected.

**Covered automatically** by `tests/api/test_analyses_api.py`. Not re-run live, to avoid spending
Gemini quota proving something the tests already assert.

**Known limitation.** The limiter is in-process. Correct for one instance, wrong for several —
two Render instances would each grant a full allowance.

---

## TC-15 — Pagination with a growing history ⬜

**Steps**
1. Create enough notes to exceed one page.
2. Page through History.
3. Submit a new note, then page again.
4. Request a page with a corrupted `cursor` parameter.

**Expected**
- Newest first, no duplicates and no skipped rows even as notes are added mid-scroll — the cursor
  encodes `(created_at, note_id)`, not an offset.
- Two notes created in the same second still order deterministically.
- A malformed cursor is a clean **400**, not a 500.

**Observed (partial).** Page 2 via cursor returned the correct next row; a garbage cursor
returned 400. Not yet exercised with enough notes to prove stability under concurrent insertion.

---

## TC-16 — The Gemini key never reaches the browser ✅

**Story.** The brief calls a key in frontend code an automatic, non-negotiable fail.

**Steps**
1. `cd frontend && npm run build`.
2. Search `dist/` for the Gemini key.
3. Open devtools on the running app: inspect the network tab and `import.meta.env`.
4. Search the repository for tracked secrets.

**Expected**
- The Gemini key appears nowhere in `dist/`, in `src/`, or in any network request from the
  browser.
- The browser talks only to your API and to Firebase Auth — never to `generativelanguage.googleapis.com`.
- No `.env`, service-account JSON, or private key is tracked by git.

**Observed.** The Gemini key is absent from `dist/` and `src/`. The one `AIzaSy…` string in the
bundle is the **Firebase web API key**, which is public by design — it identifies the project and
authorises nothing. `git ls-files` matches no secret file; no tracked file contains
`BEGIN PRIVATE KEY`; `.gitignore` covers `backend/.env`, `frontend/.env.local` and the local CA
bundle.

---

## TC-17 — First run on a fresh Firebase project ⬜

**Story.** Exactly what a reviewer does. Worth rehearsing, because it has a known sharp edge.

**Steps**
1. Follow the README from a clean clone against a brand-new Firebase project.
2. Sign up, submit a note, open the note detail page.

**Expected**
- Setup succeeds by following the written steps alone, with nothing assumed from memory.
- The detail page loads.

**Known failure if step 2 of the README is skipped.** Without
`firebase deploy --only firestore:indexes`, the analysis lookup fails with *"The query requires an
index"*, and the UI shows "Could not load this note". Indexes also report `Enabled` only after a
few minutes of building — deploying them **before** handing over the URL is not optional. This
happened during testing and is called out prominently in the README.

---

## Regression set

Run before any submission or deploy. Roughly ten minutes.

| Priority | Cases |
|---|---|
| **Must pass** | TC-03 (fabricated quote caught), TC-06 (tenant isolation), TC-07 (auth required), TC-16 (no key in browser) |
| **Core journey** | TC-01, TC-02, TC-04, TC-05 |
| **Robustness** | TC-09, TC-12, TC-13 |
| **After any prompt change** | TC-03 and TC-11 — a fall in the verified-quote count means the prompt regressed |
