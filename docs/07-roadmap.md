# Note Insight — Implementation Roadmap

Ordered so that Gemini is connected **last**, against a pipeline already proven by the mock provider. Estimated total: 17–19 hours across 5 days, inside the brief's expected range.

Each stage is a small logical commit series. No stage begins before the previous one runs.

---

## Stage 0 — Foundation (~1.5 h)

Repo, `.gitignore`, `.env.example`, both dependency manifests pinned, `pyproject.toml` (ruff + mypy strict + pytest), `tsconfig.json` strict, eslint with `no-explicit-any: error`, FastAPI app factory with health route, Vite app that boots.

**Done when:** `uvicorn` serves `/health`, `vite dev` serves a page, `ruff` and `tsc --noEmit` are clean.

```
chore: initialize repository structure and tooling
chore(backend): add fastapi application skeleton and health endpoint
chore(frontend): scaffold vite react typescript application
docs: add architecture, data model and api contract documents
```

## Stage 1 — Core, config, errors (~1.5 h)

`core/config.py`, `core/logger.py`, `core/errors.py` (domain exception hierarchy), `core/exception_handlers.py` (envelope), request-ID middleware, security headers, CORS from config.

**Why first:** every later layer raises these errors and reads this config. Retrofitting an error envelope after twenty routes exist is a rewrite.

```
feat(core): add typed settings, structured logging and request context
feat(core): add domain error hierarchy and http exception handlers
```

## Stage 2 — Domain models and repositories (~2.5 h)

`models/` for the four entities, `repositories/` with Firestore mapping, cursor pagination, and the batched write that keeps note counters consistent with review writes. `firestore.indexes.json`, `firestore.rules`.

Tested against the **Firestore emulator**, so the whole data layer is verified before any cloud project exists.

```
feat(models): define user, note, analysis and review domain entities
feat(data): add firestore repositories with owner-scoped queries
feat(data): add composite indexes and deny-all security rules
test(data): cover repository queries against the firestore emulator
```

## Stage 3 — Authentication (~2 h)

`core/firebase.py`, `core/security.py`, `api/dependencies/auth.py`, `/api/v1/me` with user upsert. Frontend `AuthContext`, `LoginPage`, `ProtectedRoute`, `apiClient` token attachment and 401 refresh-retry.

**Done when:** the tenant-isolation test file exists and passes with two seeded users, and an unauthenticated `curl` gets 401 on every protected route.

```
feat(auth): verify firebase id tokens and expose current user dependency
feat(auth): add firebase email/password sign-in and protected routes
test(auth): assert every protected route rejects unauthenticated requests
```

## Stage 4 — Notes: schemas, service, API, UI (~2.5 h)

`CreateNoteRequest` with both length limits, `NoteService`, notes routes, `NoteForm` with word counter, `HistoryPage` with cursor pagination and empty state.

```
feat(notes): add note submission endpoint with boundary validation
feat(notes): add note history listing with cursor pagination
feat(notes): build note submission form and history page
```

## Stage 5 — Analysis pipeline against the mock provider (~3.5 h)

The stage that carries the most engineering weight, and it costs nothing in quota.

- `agent/schemas/raw_output.py` + `response_schema.py`
- `agent/validators/output.py` — parse, one repair attempt, validate, classify failure
- `agent/validators/evidence.py` — the verifier
- `agent/providers/base.py` + `mock.py` (mock returns fixtures covering: clean output, a hallucinated quote, malformed JSON, a missing required field, and a timeout)
- `AnalysisService` with cache, persistence-on-failure, `condition_id` assignment
- Analysis routes and rate limiting

**Evidence verification, concretely:** normalize both note and quote (collapse whitespace, casefold, strip smart quotes and punctuation variance), then attempt exact substring → normalized substring → token-window fuzzy match with a similarity floor. Record `status` and, on a hit, the character offset in the original text so the UI can highlight it. Below the floor: `not_found`, the condition is flagged `unverified` in the response and rendered with a visible warning. **We do not delete it** — silently dropping the model's output would destroy the very signal the review dataset is for. The clinician sees "we could not find this quote in your note" and decides.

```
feat(ai): define structured analysis schema and prompt registry
feat(ai): add output validation with bounded repair on malformed responses
feat(ai): add evidence verification against source note text
feat(ai): add provider abstraction with mock implementation
feat(ai): add analysis service with caching and failure persistence
test(ai): cover malformed output, hallucinated quotes and provider failure
```

## Stage 6 — Analysis UI (~2 h)

`ConditionCard`, `EvidenceBadge`, `ConfidenceMeter`, `GapList`, `AnalysisStatusBanner`, `NoteHighlighter` (inline evidence highlighting from stored offsets — a bonus item that costs almost nothing once offsets are already persisted). Honest loading, error, and partial-success states.

```
feat(analysis): render conditions, evidence and documentation gaps
feat(analysis): highlight verified evidence inline in the source note
feat(analysis): add explicit loading, error and degraded states
```

## Stage 7 — Human review (~2.5 h)

`useReviewDraft` state machine, `ConditionEditor`, `AddConditionForm`, `ReviewDiff`. `ReviewService` with the three business invariants. Versioned review writes; note counters updated in the same batch.

**Done when:** the detail page shows, side by side, what the model said and what the human changed — the question the brief calls the product's most valuable dataset.

```
feat(review): add versioned review submission with domain invariants
feat(review): build condition editing, rejection and manual addition
feat(review): display ai output alongside human corrections
```

## Stage 8 — Gemini integration (~1 h, ≤ 10 real calls)

`gemini.py` + `key_pool.py`. Flip `LLM_PROVIDER=gemini`. Run the three sample notes. Fix what the real model actually does differently from the mock — not by re-prompting in a loop, but by reading one real response carefully and adjusting once.

**Quota discipline:** prompt iteration happens against saved real responses replayed through the validator, not against the live API.

```
feat(ai): add gemini provider with structured output and key rotation
```

## Stage 9 — Deploy, seed, document (~2 h)

Render, Vercel, Firebase config, seeded reviewer account, three synthetic sample notes, README.

The README must contain, because the brief asks for each by name:

- **Local setup from zero** — verified by following it on a clean clone, not written from memory.
- **The data model, explained** — condensed from doc 02, with the entity diagram.
- **Four design decisions, each with its alternative and why:** (1) no client-side Firestore — one enforcement point vs. two policy engines; (2) note creation separate from analysis — the note survives a provider outage; (3) reviews do not copy AI values — the diff is computed, so no stale copy exists; (4) Firestore over Postgres — with an honest account of what it costs us.
- **What I would build next with one more week**, and what I knowingly left unfinished.
- **Known Limitations and Open Problems** — written during the build, not reconstructed at the end. Already known: in-process rate limiter and key pool break across multiple instances; hand-mirrored TypeScript types will drift without OpenAPI generation; the fuzzy evidence-match threshold has no real dataset to tune against; Render cold starts; no `org_id` for multi-user clinics.
- **Hours spent, honestly** — logged per stage as I go.
- **Assumptions I made where the brief was ambiguous** — starting with the 100-word question in §3.2.

```
chore(deploy): add container build and deployment configuration
docs: add readme with setup, data model, decisions and tradeoffs
docs: add synthetic sample clinical notes
```

---

## Edge cases the build must handle, and where

| Case | Handled in |
|---|---|
| Empty or whitespace-only note | `CreateNoteRequest` validator → 422 |
| Note under 100 words | 422 naming the count and the range; UI disables submit and shows `n / 100 minimum` while typing |
| 5000-word note | Word + char limits → 422 with a clear message; the UI counts words live and disables submit before the request |
| Gemini returns prose instead of JSON | `output.py` → one repair attempt → `invalid_output` persisted |
| Gemini returns valid JSON, wrong shape | Same path; the failure record keeps a truncated raw excerpt |
| Gemini invents a quote | `evidence.py` → `not_found`, flagged in UI, kept for the dataset |
| Gemini returns zero conditions | Valid outcome; UI shows an explicit empty state, not a blank panel |
| Provider timeout / all keys exhausted | 503 + retry affordance; the note itself is already saved |
| Note analyzed twice | New analysis document; both visible in history |
| Review submitted against a stale analysis | 409 `REVIEW_CONFLICT` |
| Two tabs reviewing the same analysis | Versioned reviews; last submission wins and the earlier version survives |
| Expired token mid-session | 401 → silent refresh → one retry → login |
| Render cold start | Health ping on mount; explicit "connecting" state |
| Firestore index missing | Cannot happen: indexes are deployed from the repo |

## Scope I will cut first if time runs short

In this order, and the README will say which were cut and why:

1. Correction-metrics view (bonus)
2. PDF/image upload (bonus)
3. Streaming (bonus — genuinely useful, but it complicates the validate-then-persist pipeline that carries more marks)
4. Review diff visualization (degrades to showing the two versions in sequence rather than a computed diff)

I will not cut: tenant-isolation testing, evidence verification, the AI/human separation, or the error-state honesty. Those are the assessment.
