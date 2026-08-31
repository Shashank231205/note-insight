# Note Insight — API Contract

Base path: `/api/v1`. All routes except `/health` require `Authorization: Bearer <firebase_id_token>`.

## 1. Conventions

- Request models use `model_config = ConfigDict(extra="forbid")`. An unexpected field is a 422, not a silent ignore — this is what prevents a client from smuggling `owner_uid`.
- Responses are Pydantic models with `response_model` declared on every route, so FastAPI strips anything not in the contract. Internal fields cannot leak by accident.
- IDs in paths are validated as UUID4.
- All timestamps are RFC 3339 UTC.
- Cursor pagination: `?limit=20&cursor=<opaque>`; responses carry `next_cursor: string | null`.

## 2. Error envelope

Every non-2xx response, including FastAPI's own validation errors (overridden by an exception handler), has this shape:

```json
{
  "error": {
    "code": "NOTE_NOT_FOUND",
    "message": "Note not found.",
    "details": null,
    "request_id": "01J8X..."
  }
}
```

| HTTP | `code` values | Meaning |
|---|---|---|
| 400 | `INVALID_REQUEST` | Malformed but schema-valid input |
| 401 | `UNAUTHENTICATED`, `TOKEN_EXPIRED`, `TOKEN_INVALID` | Missing/bad/expired ID token |
| 403 | `FORBIDDEN` | Authenticated but not the owner |
| 404 | `NOTE_NOT_FOUND`, `ANALYSIS_NOT_FOUND`, `REVIEW_NOT_FOUND` | |
| 409 | `REVIEW_CONFLICT` | Review submitted against a stale analysis |
| 422 | `VALIDATION_ERROR` | Pydantic rejection; `details` carries field errors |
| 429 | `RATE_LIMITED` | Per-user limit; `Retry-After` header set |
| 502 | `PROVIDER_INVALID_OUTPUT` | Model responded but output failed schema validation twice |
| 503 | `PROVIDER_UNAVAILABLE` | All Gemini keys exhausted, or timeout |

**404 vs 403 on another user's document:** we return **404**. Returning 403 confirms the resource exists, which is an information leak across tenants. The ownership check lives in the service layer and the repository query is scoped by `owner_uid` regardless, so this is belt and braces.

## 3. Endpoints

### `GET /health`
Unauthenticated liveness. `{ "status": "ok", "version": "1.0.0" }`.

### `GET /api/v1/me`
Returns the caller's profile, upserting `users/{uid}` on first call.

```
200 → { uid, email, display_name, created_at }
```

### `POST /api/v1/notes`
Creates a note. Does **not** analyze it — that is a separate, retryable action.

```
Request  CreateNoteRequest
  content: str            # 100–3000 words, and <= 40_000 chars
  pseudonym: str | null   # max 64 chars
  visit_date: date | null # not in the future

201 → NoteResponse
```

**The "100–3000 words" range is enforced as written.** Both bounds are hard: fewer than 100 words or more than 3000 is a 422 with a message naming the actual count and the accepted range. The character ceiling of 40,000 sits alongside the word maximum because a single 40,000-character "word" passes a word-count check on its own.

The frontend counts words live, shows `n / 100 minimum` below the threshold and `n / 3000` above it, and keeps submit disabled until the count is inside the range — so the boundary is visible while typing rather than discovered by a rejected request.

**Why two steps rather than analyze-on-create:** the note must survive a Gemini outage. If creation and analysis were one call, a 503 from the provider would lose the clinician's typing. Splitting them means the note is durable and the UI can offer "retry analysis" against an existing resource. The frontend still presents it as one action; it fires the second call immediately.

### `GET /api/v1/notes?limit&cursor`
The history list. Server-side filter is `owner_uid == caller`.

```
200 → { items: NoteSummary[], next_cursor: string | null }

NoteSummary { note_id, pseudonym, visit_date, created_at,
              condition_count, analysis_count, review_status }
```

### `GET /api/v1/notes/{note_id}`
Full detail in one round trip — note, latest analysis, latest review.

```
200 → NoteDetailResponse { note, latest_analysis: AnalysisResponse | null,
                           latest_review: ReviewResponse | null }
```

### `POST /api/v1/notes/{note_id}/analyses`
Runs an analysis. Rate limited.

```
Request  RunAnalysisRequest { force: bool = false }

201 → AnalysisResponse   # status may be "succeeded" or "invalid_output"
503 → PROVIDER_UNAVAILABLE
```

Note the deliberate asymmetry: an analysis whose *output* failed validation is a **201 with `status: "invalid_output"`**, because we successfully created a durable record of a real event. A provider we could not reach at all is a 503, because nothing was created. The UI distinguishes "the model gave us something we can't trust" from "we couldn't reach the model".

### `GET /api/v1/notes/{note_id}/analyses`
All analyses for the note, newest first — the prompt-iteration audit trail.

### `GET /api/v1/analyses/{analysis_id}`
Single analysis including its `verification` report.

### `POST /api/v1/analyses/{analysis_id}/reviews`
Submits a human review. Creates a new version; never mutates an existing one.

```
Request  SubmitReviewRequest
  reviewed_conditions: ReviewedConditionInput[]
  reviewed_gaps: ReviewedGapInput[]
  summary_override: str | null
  reviewer_note: str | null

201 → ReviewResponse { review_id, version, ... }
409 → REVIEW_CONFLICT   # the analysis is no longer the note's latest
```

Validation beyond field types, enforced in `ReviewService`:
- every `condition_id` with `origin: "ai"` must exist in the referenced analysis;
- every `origin: "human"` condition must carry `action: "added"`;
- `action: "rejected"` requires a `rejection_reason`.

These are business invariants, so they live in the service and raise domain errors — not in the Pydantic schema, which only knows about shapes.

### `GET /api/v1/analyses/{analysis_id}/reviews`
Every review version for the analysis, newest first.

## 4. Type parity with the frontend

`frontend/src/types/api.ts` mirrors these response models by hand, in one file, with the same names. Every enum is a TypeScript union of string literals — never `string`. `apiClient.ts` returns those types; no component sees an untyped payload, and `any` appears nowhere.

If this project grew, the honest next step is generating that file from the OpenAPI schema FastAPI already emits. Hand-mirroring is the deliberate trade for a five-day build, and it is called out as such in the README.

## 5. Rate limiting

Per-UID token bucket on `POST /notes/{id}/analyses`: 10 analyses per hour, burst 3. In-memory for a single Render instance, with the multi-instance limitation documented. This protects free-tier Gemini quota, which is the actual scarce resource here.
