# Note Insight — Data Model

Database: **Firestore (Native mode)**.

## 0. Why Firestore

Chosen over Postgres and SQLite, and the reasoning is honest rather than reflexive:

- The dominant read is `notes where owner_uid == X order by created_at desc` — a single composite index, and Firestore serves it well.
- Analysis output is a nested, evolving document (conditions, gaps, verification report). Storing it as a JSON document avoids either a five-table join or a `jsonb` column that gets none of Postgres's relational benefits anyway.
- Firebase Auth is already the identity provider; using Firestore keeps the deployment to two managed free-tier services with no connection-pool or migration story.

**What we give up, stated plainly:** no joins, no transactional integrity across collections beyond a batch, no `GROUP BY` for the metrics view (we would aggregate in application code or precompute counters). If this product grew a reporting requirement, Postgres would be the right migration and the repository layer is the seam that makes it possible.

## 1. Entities are four, not one

```
User ──1:N──► Note ──1:N──► Analysis ──1:N──► Review
                              (AI-written,      (human-written,
                               immutable)        versioned)
```

Collapsing these is the trap the brief warns about. Keeping them apart is what makes "what did the model say, and what did the human change?" a query rather than an archaeology project.

- A **Note** is what the clinician wrote. It is the immutable input.
- An **Analysis** is one machine opinion about one note, at one prompt version, from one model. Re-running the prompt produces a *new* analysis; the old one stays.
- A **Review** is one human's corrected version of one analysis. Submitting again produces a *new* review version; the old one stays.

## 2. Collections

All collections are top-level and every document carries `owner_uid`.

**Why top-level rather than `notes/{id}/analyses` subcollections:** every query then filters on `owner_uid` as a first-class predicate at the database layer — the ownership check is structural, not something a code path can forget. It also makes the cross-note metrics query ("how often does this clinician correct the model?") a plain query rather than a collection-group scan.

### `users/{uid}`

Mirror of the Firebase identity, written by the system on first authenticated request.

| Field | Type | Written by |
|---|---|---|
| `uid` | string (= Firebase UID, doc id) | system |
| `email` | string | system |
| `display_name` | string \| null | system |
| `created_at` | timestamp | system |
| `last_seen_at` | timestamp | system |

No password material ever touches Firestore — Firebase Auth owns credentials entirely.

### `notes/{note_id}`

| Field | Type | Written by | Notes |
|---|---|---|---|
| `note_id` | string (uuid4) | system | |
| `owner_uid` | string | system | from verified token, **never** from the request body |
| `content` | string | human | the clinical note, 1–3000 words enforced at the API boundary |
| `content_hash` | string (sha256) | system | drives the analysis cache |
| `word_count` | int | system | |
| `pseudonym` | string \| null | human | optional, max 64 chars, never a real identifier |
| `visit_date` | date \| null | human | |
| `created_at` / `updated_at` | timestamp | system | |
| `latest_analysis_id` | string \| null | system | denormalized pointer |
| `latest_review_id` | string \| null | system | denormalized pointer |
| `review_status` | enum `pending` \| `reviewed` | system | derived on review submission |
| `condition_count` | int | system | from the latest review if present, else latest analysis |
| `analysis_count` | int | system | |

`condition_count`, `review_status` and the pointers are **denormalized on purpose**: the history list must render from a single query with no fan-out reads. They are derived values with a single writer (`NoteService`), so they cannot drift from two directions.

### `analyses/{analysis_id}` — machine-written, never mutated

| Field | Type | Written by |
|---|---|---|
| `analysis_id` | string (uuid4) | system |
| `note_id`, `owner_uid` | string | system |
| `status` | enum `succeeded` \| `invalid_output` \| `provider_error` | system |
| `provider` | enum `gemini` \| `mock` | system |
| `model_id` | string (e.g. `gemini-2.5-flash`) | system |
| `prompt_version` | string (e.g. `v1`) | system |
| `output` | `AnalysisOutput` \| null | **machine** |
| `verification` | `VerificationReport` | system |
| `failure` | `{ code, message, raw_excerpt }` \| null | system |
| `latency_ms` | int | system |
| `token_usage` | `{ prompt, completion, total }` \| null | system |
| `cache_hit` | bool | system |
| `created_at` | timestamp | system |

`output` shape:

```
AnalysisOutput
  summary: str                      # <= 600 chars
  conditions: Condition[]           # 0..25
  documentation_gaps: Gap[]         # 0..25

Condition
  condition_id: str                 # stable id assigned server-side, used by reviews
  name: str
  evidence_quote: str               # verbatim from the note
  documentation_status: enum well_documented | ambiguous | mentioned_without_plan
  icd10_code: str | null            # pattern-checked, approximate by design
  confidence: float                 # 0.0–1.0

Gap
  gap_id: str
  description: str
  related_condition_id: str | null
  severity: enum low | medium | high
```

`verification` shape:

```
VerificationReport
  checked_at: timestamp
  quote_results: QuoteVerification[]
  verified_count: int
  unverified_count: int

QuoteVerification
  condition_id: str
  status: enum exact | normalized | fuzzy | not_found
  match_score: float                # 0.0–1.0
  match_offset: int | null          # char offset into note.content, powers UI highlighting
```

`condition_id` is assigned by us, not the model. Reviews reference it, so it must be stable and trustworthy.

### `reviews/{review_id}` — human-written, versioned

| Field | Type | Written by |
|---|---|---|
| `review_id` | string (uuid4) | system |
| `analysis_id`, `note_id`, `owner_uid` | string | system |
| `version` | int (1, 2, 3 …) | system |
| `reviewed_conditions` | `ReviewedCondition[]` | **human** |
| `reviewed_gaps` | `ReviewedGap[]` | **human** |
| `summary_override` | string \| null | **human** |
| `reviewer_note` | string \| null | **human** |
| `created_at` | timestamp | system |

```
ReviewedCondition
  condition_id: str                 # matches an AI condition, or a new id for human additions
  origin: enum ai | human           # who first proposed this condition
  action: enum accepted | edited | rejected | added
  name / evidence_quote / documentation_status / icd10_code   # the human-authoritative values
  rejection_reason: str | null
```

The AI's values are **not** copied into the review. To answer "what changed", you read the analysis and the review side by side and diff on `condition_id`. Copying would create two sources of truth and the first bug would be a stale copy.

## 3. Which fields are written by whom

- **Machine** — `analyses.output` only. Nothing else in the database is written by the model, ever.
- **Human** — `notes.content`, `notes.pseudonym`, `notes.visit_date`, and the `reviewed_*` fields on `reviews`.
- **System** — all identifiers, all timestamps, all `owner_uid` values, all denormalized counters, the verification report, and every status enum.

`owner_uid` deserves emphasis: it is taken from the verified Firebase token inside the dependency layer and written by the repository. A client-supplied `owner_uid` in a request body is not merely ignored — the request schemas do not contain the field, so Pydantic rejects it under `extra="forbid"`.

## 4. Re-analysis semantics

Analyzing the same note twice creates a second `analyses` document. The old one does not disappear, and it should not: the reason to re-run is usually that the prompt changed, which makes the pair of analyses the evidence for whether the change was an improvement.

`notes.latest_analysis_id` moves to the new document. History shows every analysis for a note, labelled with its `prompt_version` and `created_at`. A review always names the specific `analysis_id` it reviewed, so a review is never orphaned or silently re-pointed at output the human did not see.

**Caching:** if a succeeded analysis already exists for the same `(content_hash, prompt_version, model_id)`, we return it and mark `cache_hit` rather than paying for the call again. A `force=true` flag on the request bypasses the cache deliberately.

## 5. Queries and indexes

| Query | Index |
|---|---|
| History list — user's notes, newest first | `notes`: `owner_uid ASC, created_at DESC` |
| All analyses of a note, newest first | `analyses`: `note_id ASC, created_at DESC` |
| Latest review for an analysis | `reviews`: `analysis_id ASC, version DESC` |
| Correction metrics for a user | `reviews`: `owner_uid ASC, created_at DESC` |

Pagination is cursor-based (`start_after` on `created_at` + doc id), not offset-based, because Firestore offsets bill for every skipped document.

These four composite indexes ship as `firestore.indexes.json` in the repo, deployed with the project — not discovered at runtime from an error message in production.

## 6. Firestore security rules

```
match /{document=**} { allow read, write: if false; }
```

The client SDK holds no data access. This is intentional and explained in §3 of the architecture doc.

## 7. Known limitations of this model

- **No `org_id` yet.** Multi-user-per-clinic is anticipated, not implemented; the field would slot beside `owner_uid` and turn every ownership predicate into a two-field filter.
- **Denormalized counters are eventually consistent** if a review write succeeds and the note counter update fails. Mitigated with a Firestore batched write covering both documents.
- **No soft delete.** Delete is out of scope for this build; the collections are append-mostly, which is the right default for clinical audit anyway.
