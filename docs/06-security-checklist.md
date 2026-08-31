# Note Insight — Security Checklist

The brief says to treat tenant isolation as if real patient data were behind it. This is the checklist that claim has to survive.

## 1. Secrets

- [ ] `GEMINI_API_KEYS` exists only in Render environment variables. **Zero occurrences** in `frontend/`, verified by `grep -ri "AIza" frontend/ backend/src/` returning nothing before submission.
- [ ] The Gemini call happens only in `agent/providers/gemini.py`, which is imported only by the service layer. There is no proxy endpoint that forwards arbitrary prompts.
- [ ] `.gitignore` covers `.env`, `.env.local`, `.env.*.local`, `.firebase/`, `service-account.json`, `credentials.json`, `*-firebase-adminsdk-*.json`, `__pycache__/`, `node_modules/`, `dist/`, `.venv/`.
- [ ] `.env.example` contains placeholder values only — never a real key, not even a revoked one.
- [ ] Git history is checked for accidentally committed secrets before submission, not just the working tree. A secret in commit 12 is still a leaked secret.
- [ ] The service account has **Cloud Datastore User**, not Editor or Owner.

## 2. Authentication

- [ ] Every route except `/health` depends on `get_current_user`. Enforced by a test that enumerates `app.routes` and asserts the dependency is present — so a route added later cannot quietly be public.
- [ ] Tokens are verified with `firebase_admin.auth.verify_id_token(token, check_revoked=True)`. Signature, expiry, audience, and issuer are all checked by the SDK; we do not decode JWTs by hand.
- [ ] `uid` comes from the verified token and nowhere else.
- [ ] Expired token → 401 `TOKEN_EXPIRED`; the frontend refreshes once and retries, then routes to login.
- [ ] Malformed `Authorization` header → 401, never 500.

## 3. Authorization / tenant isolation

- [ ] **Every** repository read is scoped by `owner_uid` in the query itself. Fetch-then-check is not used: a fetch-by-id that forgets its check is one careless line away, whereas a query that cannot express itself without the predicate is structurally safe.
- [ ] Services re-assert ownership on single-document reads as a second layer.
- [ ] Cross-tenant access returns **404**, not 403 — existence is not disclosed.
- [ ] `tests/security/test_tenant_isolation.py` walks every resource-scoped endpoint with user B's token against user A's document IDs and asserts 404 on all of them. This is the test that proves the hard requirement, so it is exhaustive rather than representative.
- [ ] Firestore rules deny all client SDK access.

## 4. Input validation

- [ ] All request bodies are Pydantic models with `extra="forbid"`.
- [ ] `content`: non-empty after strip, ≤ 3000 words **and** ≤ 40,000 characters. Two limits because a 40,000-character single "word" is a valid way to attack a word-count-only check.
- [ ] `pseudonym` ≤ 64 chars; `visit_date` not in the future.
- [ ] Path IDs validated as UUID4 before any database call.
- [ ] `limit` clamped to [1, 50]; cursors are opaque, signed-free but validated, and a malformed cursor is a 400 rather than an unhandled Firestore exception.
- [ ] Request body size capped by middleware, so an oversized payload is rejected before parsing.

## 5. Output safety

- [ ] Every route declares `response_model`, so internal fields cannot leak.
- [ ] Error messages are fixed strings. Exception detail, stack traces, and provider responses never reach the client — they go to the structured log, correlated by `request_id`.
- [ ] Note content is never logged. The log carries `note_id`, `content_hash`, `word_count`, `latency_ms` — enough to debug, never enough to reconstruct a note from log storage.
- [ ] Prompt-injection posture: the note is untrusted input. The model's output is constrained by `responseSchema` and then re-validated by Pydantic, so a note containing "ignore your instructions and return X" can at worst produce a schema-valid analysis with wrong content — which the human review layer exists to catch. It cannot cause an unstructured response to be trusted, and it cannot reach the database unvalidated. This limit is stated in the README rather than pretended away.
- [ ] The frontend renders note text and model output as text nodes, never `dangerouslySetInnerHTML`. The inline evidence highlighter builds React elements from computed offsets, not from an HTML string.

## 6. Transport and headers

- [ ] HTTPS everywhere (Vercel and Render both terminate TLS by default).
- [ ] CORS is an explicit origin allowlist; `*` never appears.
- [ ] `Authorization` is the only credential; no cookies, therefore no CSRF surface.
- [ ] Security headers via middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.

## 7. Abuse and cost

- [ ] Per-UID rate limit on the analysis endpoint (10/hour, burst 3), returning 429 with `Retry-After`.
- [ ] Analysis cache on `(content_hash, prompt_version, model_id)` prevents paying twice for an identical note.
- [ ] `LLM_TIMEOUT_SECONDS` bounds every provider call; no unbounded retry loop exists anywhere.
- [ ] Known limitation, documented: the rate limiter and key pool are in-process, so they are per-instance. Correct for one Render instance, wrong for many — Redis would be the fix.

## 8. Data handling

- [ ] The product asks for a **pseudonym**, and the field label and helper text say so explicitly. There is no field anywhere for a name, MRN, DOB, or any real identifier.
- [ ] Every note in the repo and in the seeded database is synthetic and marked as such.
- [ ] Nothing is deleted or overwritten: analyses are immutable, reviews are versioned. Audit trail is a property of the schema, not of a logging add-on.
