# Note Insight

A clinical documentation assistant. A clinician pastes a free-text note and, within a few
seconds, gets back a structured read of it: which conditions the note addresses, a verbatim
quote from the note supporting each one, how well each is documented, a suggested ICD-10 code,
and the specific gaps a coding specialist would otherwise query back days later. The clinician
edits, rejects or adds to that draft, and the corrections are saved *next to* the original model
output rather than on top of it.

Built for the DoctusTech technical assessment.

---

## Live application

| | |
|---|---|
| **App** | **https://note-insight-eight.vercel.app** |
| API | https://note-insight-nrao.onrender.com |
| Repository | https://github.com/Shashank231205/note-insight |

**Test account** — or sign up yourself, self-registration is open:

```
reviewer@note-insight.demo
NoteInsight2026!
```

That account already has the three sample notes submitted and analysed, one of them reviewed,
so the history page, the AI-versus-human diff and the inline evidence highlighting are all
visible without waiting on a cold start and a model call first.

> **The first request takes 30–50 seconds.** Render's free tier stops the container after 15
> minutes idle. The login screen pings `/health` on mount so the backend wakes while you type
> your password, and says "connecting" rather than pretending to be fast. Every request after
> that is normal — an analysis takes about six seconds, most of it Gemini.

### Worth looking at first

- **`PT-1156`** — 4 of its 10 evidence quotes are flagged **unverified**. That is the verifier
  working, not a bug: the model cites one drug from a long medication list by joining the list's
  opening words to a drug appearing later in the sentence, producing a quote that is not in the
  note. It is explained under [how we know the model didn't make it up](#how-we-know-the-model-didnt-make-it-up).
- **`PT-2041`** — reviewed, so the note page shows what the model said beside what the clinician
  changed.

---

## Contents

- [Running it locally](#running-it-locally)
- [The data model](#the-data-model)
- [Design decisions](#design-decisions)
- [How we know the model didn't make it up](#how-we-know-the-model-didnt-make-it-up)
- [What happens when things go wrong](#what-happens-when-things-go-wrong)
- [Testing](#testing)
- [Known limitations and open problems](#known-limitations-and-open-problems)
- [What I would build next](#what-i-would-build-next)
- [Time spent](#time-spent)

---

## Running it locally

Verified by following these steps on a clean clone. Requires **Python 3.10+** and **Node 18+**.

### 1. Firebase project

You need your own project — there is no shared one, and the service-account credential is not in
this repository.

1. [Firebase console](https://console.firebase.google.com) → **Add project**. Analytics is not needed.
2. **Authentication → Get started → Email/Password → Enable.**
3. **Firestore Database → Create database → Production mode.** Pick your nearest region.
4. **Project settings → General → Your apps → `</>`** — register a web app and keep the
   `firebaseConfig` values it shows you.
5. **Project settings → Service accounts → Generate new private key.** A JSON file downloads.

### 2. Deploy the security rules and indexes

Both are version-controlled here, so they are never discovered from a runtime error:

```bash
npm install -g firebase-tools
firebase login
firebase use --add          # select your project, alias it "default"
firebase deploy --only firestore:rules,firestore:indexes
```

Indexes take a few minutes to build. **The note detail page returns errors until they report
`Enabled`** in the console — this is the most likely first-run stumble.

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example .env
```

Fill in `backend/.env`:

| Variable | Where it comes from |
|---|---|
| `FIREBASE_PROJECT_ID` | Project settings → General → Project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | The downloaded JSON, flattened to **one line**, in single quotes |
| `GEMINI_API_KEYS` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — comma-separated, primary first |
| `LLM_PROVIDER` | `mock` to develop without spending quota, `gemini` for real calls |

To flatten the service-account JSON without hand-editing it:

```bash
python -c "import json;print(json.dumps(json.load(open('path/to/serviceAccount.json')),separators=(',',':')))"
```

Then:

```bash
uvicorn src.main:app --reload --port 8000
```

`http://localhost:8000/health` should return `{"status":"ok"}`; `/docs` has the full API.

> **If your machine runs antivirus that scans HTTPS** (Avast, Kaspersky and ESET do by default),
> Firestore calls fail with `CERTIFICATE_VERIFY_FAILED`. The AV substitutes its own certificate;
> Python's `ssl` accepts it from the Windows store, but gRPC and `requests` carry their own CA
> bundles and do not. Run `python scripts/build_ca_bundle.py`, then start the server with
> `scripts/dev.ps1`, which points all three CA variables at the merged bundle. Certificate
> verification stays **on** — the trust store just also contains what your machine actually
> presents. None of this ships to production.

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
```

Fill `frontend/.env.local` with the four values from your `firebaseConfig` (`apiKey`,
`authDomain`, `projectId`, `appId`), leaving `VITE_API_BASE_URL=http://localhost:8000`.

```bash
npm run dev
```

Open `http://localhost:5173` and sign up. Everything in `.env.local` is compiled into the browser
bundle and none of it is secret — the Firebase web API key identifies the project, it does not
authorise anything. **The Gemini key is not there and never will be.**

### 5. Try it

Paste any note from [`docs/sample-notes/`](docs/sample-notes/) — the body, from `Subjective:`
down; the pseudonym and visit date go in the form fields. All three are synthetic.

- `01-diabetes-ambiguous.md` — conditions named without the qualifiers a coder needs
- `02-chf-well-documented.md` — a well-documented note, for contrast
- `03-polypharmacy-gaps.md` — medications with no linked diagnosis

---

## The data model

Firestore in Native mode. Four top-level collections, every document carrying `owner_uid`. Full
detail in [`docs/02-data-model.md`](docs/02-data-model.md).

```
User ──1:N──► Note ──1:N──► Analysis ──1:N──► Review
                            (machine-written,   (human-written,
                             never mutated)      versioned)
```

**These are four entities, not one.** Collapsing them is the trap the brief warns about, and
keeping them apart is what makes *"what did the model say, and what did the human change?"* a
query rather than an archaeology project.

- A **Note** is what the clinician wrote — the immutable input.
- An **Analysis** is one machine opinion about one note, at one prompt version, from one model.
  Re-running produces a **new** analysis; the old one stays.
- A **Review** is one human's corrected version of one analysis. Submitting again produces a
  **new** version; the old one stays.

### Who writes what

| Written by | Fields |
|---|---|
| **Machine** | `analyses.output` — summary, conditions, evidence quotes, documentation status, ICD-10 codes, confidence |
| **Human** | `notes.content`, `notes.pseudonym`, `notes.visit_date`, and everything inside `reviews.reviewed_conditions` |
| **System** | all ids, `owner_uid`, timestamps, `content_hash`, `verification`, `latency_ms`, `token_usage`, and the denormalized counters on `notes` |

`owner_uid` comes from the verified Firebase token and **never** from a request body. A payload
containing `owner_uid` is ignored, and a test asserts exactly that.

### Querying "all notes for user X, newest first"

```python
notes.where("owner_uid", "==", uid).order_by("created_at", DESCENDING).limit(n)
```

One composite index — `(owner_uid ASC, created_at DESC, note_id DESC)` — declared in
[`backend/firestore.indexes.json`](backend/firestore.indexes.json). `note_id` is the tiebreaker
so the cursor stays stable when two notes share a timestamp: the cursor encodes
`(created_at, note_id)` rather than an offset, so pagination cannot skip or repeat a row when
new notes arrive mid-scroll.

The history list renders from **that one query alone**. That is why `condition_count`,
`review_status`, `latest_analysis_id` and `latest_review_id` are denormalized onto the note —
without them a 20-row page would fan out into 40 extra reads. They are derived values with a
single writer, so they cannot drift from two directions.

---

## Design decisions

### 1. No client-side Firestore access — one enforcement point, not two

**Alternative:** let the browser's Firebase SDK read Firestore directly and express
authorisation in security rules. That is the conventional Firebase architecture and would have
removed several backend endpoints.

**Chosen:** the browser holds the Auth SDK only. Every read and write goes through FastAPI using
the Admin SDK, and the deployed `firestore.rules` are **deny-all**.

**Why:** otherwise authorisation lives in two places that must agree forever — Python service
code and a rules DSL — and the day they disagree is a data breach. One enforcement point in
Python is unit-testable, and [`tests/security/`](backend/tests/security/) walks every
resource-scoped route with a second clinician's token. The cost is real: no realtime listeners,
and every read pays a backend hop.

### 2. Note creation is separate from analysis

**Alternative:** a single `POST /notes` that saves and analyses at once. Simpler client, one
round trip.

**Chosen:** `POST /notes` persists and returns immediately; `POST /notes/{id}/analyses` runs the
model.

**Why:** the LLM is the unreliable part. If Gemini is down, rate-limited or slow, the clinician's
typing is already safe and the analysis becomes a retry rather than lost work. It also makes
"analyse this again under a better prompt" a natural second call, and keeps the expensive
operation behind its own rate limit.

### 3. Reviews store the human's version only — the diff is computed

**Alternative:** copy the AI's values into the review document alongside the human's, so both sit
in one row.

**Chosen:** a review stores what the clinician left, plus `condition_id`, an `origin`
(`ai` | `human`) and an `action` (`accepted` | `edited` | `rejected` | `added`). The AI's values
are read from the analysis.

**Why:** a copy is a second source of truth that can go stale. There is exactly one record of
what the model said — the immutable analysis — and the diff is derived by joining on
`condition_id`. This is the dataset the brief calls the most valuable thing the product will
produce, and it is only trustworthy if the model's side of it was never rewritten.

### 4. Firestore over Postgres, with the cost stated

**Alternative:** Postgres, which would give joins, cross-entity transactions, and `GROUP BY` for
the metrics view.

**Chosen:** Firestore.

**Why:** the dominant read is a single owner-scoped, time-ordered query that Firestore serves
from one index. Analysis output is a nested, evolving document, which in Postgres would be
either a five-table join or a `jsonb` column earning none of Postgres's relational benefits.
Firebase Auth is already the identity provider, so this keeps deployment to two managed
free-tier services with no migration or connection-pool story.

**What that costs us, plainly:** no joins, no cross-collection transactions beyond a batch, and
no `GROUP BY` — the correction-metrics view would need application-side aggregation or
precomputed counters. If this product grew a reporting requirement, Postgres would be the right
migration, and the repository layer is the seam that makes it possible.

---

## How we know the model didn't make it up

The prompts are at [`backend/src/agent/prompts/`](backend/src/agent/prompts/) —
`v2_note_analysis.md` is current; `v1` is kept because analyses recorded under it must stay
reproducible.

Three independent layers, because a prompt instruction is a request, not a guarantee.

**1. Structured output, not parsed prose.** The request sets
`response_mime_type=application/json` with a `response_schema`, so the model decodes into the
shape we asked for. Nothing is extracted with a regex or a string split.

**2. Schema validation before the database or the UI.** The response is parsed and validated
against Pydantic models in
[`agent/validators/output.py`](backend/src/agent/validators/output.py). A response wrapped in a
markdown fence is structurally recovered — slicing between the outer braces, which cannot alter
a value inside. Anything beyond that **fails**: there is no second guess at what the model meant,
because a repair that changed values would silently invent clinical content.

**3. Evidence verification against the source note.**
[`agent/validators/evidence.py`](backend/src/agent/validators/evidence.py) normalises both note
and quote (whitespace, casefolding, smart quotes) and attempts exact → normalised → fuzzy
matching against a similarity floor. A hit records the character offset, which is what drives
inline highlighting. A miss is recorded as `not_found` and the condition is rendered with a
visible warning.

**A quote that fails verification is kept, not deleted.** Silently dropping it would destroy the
signal the review dataset exists to capture. The clinician is told we could not find the quote,
and decides.

### This is not theoretical — it caught a real fabrication

On the first live run against `01-diabetes-ambiguous.md`, Gemini returned this as a verbatim
quote:

> "Notes occasional tingling in both feet… Foot examination shows diminished sensation to
> monofilament testing… Patient started on gabapentin 300 milligrams at bedtime."

Every sentence is real. They sit at characters 562, 1510 and 1962 — three different sections of
the note. The contiguous quote does not exist. The verifier flagged it; the prompt was tightened
in v2 to ban assembled quotes explicitly; verification on that note went from 2/6 to **6/6**.

The v1 prompt already forbade stitching, in prose. The model did it anyway. That is the argument
for the verifier: instructions are not enforcement.

### Where it still fails, measured honestly

Across the three sample notes under v2, **13 of 19 quotes verify exactly**:

| Note | Verified |
|---|---|
| `01-diabetes-ambiguous` | 6 / 6 |
| `02-chf-well-documented` | 3 / 3 |
| `03-polypharmacy-gaps` | **4 / 10** |

Note 03 is a medication-reconciliation note whose drug list is one long sentence. To cite a single
drug, the model repeatedly produces `"Current medication list reviewed: amlodipine 5 milligrams
daily"` — a real prefix joined to a drug that appears later in the sentence, so not a substring.
The six failures on that note are all this one shape.

I wrote a third prompt version targeting exactly this, with the failing string as a worked
example. **It changed nothing** — same 4/10, same conditions. I did not ship it, because a prompt
revision that cannot be shown to work is noise in the version history and a lie in the cache key.

So the honest position is: the prompt reduces this failure, it does not eliminate it, and the
verifier is what makes that acceptable. Those six conditions reach the clinician clearly marked
as unverified rather than silently presented as quoted fact.

One earlier draft of this README claimed 13/13 across all three notes. That figure was measured
through a test harness that failed to strip the sample file's `Expected findings:` header, so the
model was reading the answer key. The numbers above are from the note body alone.

---

## What happens when things go wrong

Decided deliberately, and each one tested:

| Situation | What the system does |
|---|---|
| Empty or whitespace-only note | 422 at the API boundary; submit is disabled before the request |
| Note under 100 or over 3000 words | 422 naming the actual count and the range; the UI counts words live |
| Request body over 256 KB | 413 from middleware, before parsing |
| Model returns prose instead of JSON | Persisted as `invalid_output` with a truncated raw excerpt |
| Model output cut off mid-object | Persisted as `truncated` — distinct from "not JSON", because only this one is fixed by more output budget |
| Valid JSON of the wrong shape | Persisted as `schema_mismatch`, naming the offending field |
| Model invents or assembles a quote | `not_found`, flagged in the UI, **kept** for the dataset |
| Model returns zero conditions | A valid outcome — explicit empty state, not a blank panel |
| Gemini quota or auth failure | Rotate to the fallback key and retry; the failed key cools down for 5 minutes |
| Network, DNS or TLS failure | 503 with a retry hint, never a 500 — unreachable is not a bug in the app |
| All keys exhausted | 503; the note is already saved and the analysis can be retried |
| Same note analysed twice | Cache hit, no second Gemini call. `force: true` creates a new analysis; the old one survives |
| Same note under a new prompt version | A **new** analysis — `prompt_version` is part of the cache key |
| Review against a superseded analysis | 409 `REVIEW_CONFLICT` — reload before submitting |
| Two tabs reviewing one analysis | Versioned reviews; the later submission wins, the earlier version survives |
| Another user's resource, by id | 404 — never 403, which would confirm it exists |
| Expired token mid-session | 401 → silent refresh → one retry → login |

### An honest note on the thinking-token failure

The very first live Gemini call returned truncated JSON. Gemini 2.5 Flash has thinking enabled
by default and its tokens come out of `max_output_tokens` — 3,239 of a 4,096 budget went to
reasoning, leaving too little to finish writing the object. The fix was
`thinking_config=ThinkingConfig(thinking_budget=0)`, which also cut latency from **20.7s to ~5s**
and token use from **6,037 to ~2,700** per note. The validator had already rejected it correctly;
what was missing was a failure code separating truncation from garbage, which `truncated` now
provides.

---

## Testing

```bash
cd backend && pytest                                  # 158 tests
cd backend && ruff check . && mypy src
cd frontend && npm run typecheck && npm run lint
```

The suite runs entirely against in-memory repositories and a mock LLM provider — no emulator, no
network, no Gemini quota. It covers schema validation and every failure path, evidence
verification including hallucinated quotes, provider transport failures, rate limiting, cursor
pagination, and tenant isolation across every resource-scoped route.

`ruff`, `mypy --strict`, `tsc` and `eslint` (with `no-explicit-any` as an error) are all clean.
There is no `any` in the frontend.

---

## Known limitations and open problems

Written during the build, not reconstructed at the end.

- **The rate limiter and the Gemini key pool are in-process.** Correct for one instance, wrong
  for several — two Render instances would each grant a full quota. Redis is the fix.
- **TypeScript types are hand-mirrored from the Pydantic schemas.** They agree today; nothing
  forces them to agree tomorrow. Generating them from the OpenAPI schema is the answer, and was
  cut for time.
- **The fuzzy evidence-match threshold is a guess.** There is no labelled dataset to tune it
  against, so it is set conservatively — it prefers reporting `not_found` over letting a
  fabrication through. Every mismatch so far has been a genuine model error, but that is
  anecdote, not calibration.
- **Gemini still ignores the contiguity rule occasionally, even in v2.** The verifier is the
  backstop, not the prompt. I chose not to keep re-prompting against a model that will sometimes
  disregard an explicit instruction; that is what the verification layer is for.
- **`GET /analyses/{id}/reviews` returns 200 with `[]`** for an analysis the caller does not own,
  where sibling routes return 404. The query is owner-scoped so nothing leaks, but it is
  inconsistent with the rest of the API.
- **No `org_id`.** A clinic where several clinicians share patients would need one. The schema
  survives it — `owner_uid` becomes one predicate of two — but queries and indexes would change.
- **Render cold starts** take 30–50s on the free tier. The frontend pings `/health` on mount so
  the backend wakes while the reviewer types their password, and the login screen says
  "connecting" rather than pretending to be fast.
- **The correction-metrics view was cut.** It is the most interesting thing this data model
  enables, and the first thing I would build next.

---

## What I would build next

With one more week, in order:

1. **The correction-metrics view** — how often the human corrects the machine, broken down by
   condition. Every field it needs is already stored; only the aggregation is missing. It turns
   this from a tool into a dataset.
2. **Generated API types.** Emit TypeScript from the FastAPI OpenAPI schema and delete the
   hand-written mirror, removing a whole class of drift bug.
3. **Streaming the analysis into the UI.** Genuinely useful at ~5 seconds a call. Deliberately
   cut because it complicates the validate-then-persist pipeline that carries more marks — you
   cannot schema-validate what you have not finished receiving.
4. **Redis** for the rate limiter and key pool, which is what makes horizontal scaling honest.
5. **A labelled evidence-verification set**, to tune the fuzzy threshold against something real.

### Knowingly left unfinished

- Correction-metrics view (bonus)
- PDF/image upload (bonus)
- Streaming (bonus)
- The 200-vs-404 inconsistency on the reviews listing, noted above

I did not cut tenant-isolation testing, evidence verification, the AI/human separation, or
honesty in the error states. Those are the assessment.

---

## Time spent

Roughly **20 hours** across five days, including the design documents in [`docs/`](docs/), which
were written before the code and are why the data model did not need rewriting on day three.

The largest single time sink was not the AI integration. It was discovering, on first contact
with the live model, that three things I believed were true were not: thinking tokens consuming
the output budget, the application reading its own configuration inconsistently, and an
antivirus intercepting TLS on the development machine.
