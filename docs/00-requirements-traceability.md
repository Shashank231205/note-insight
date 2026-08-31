# Requirements Traceability — PDF → Plan

Every requirement in the assessment document, mapped to where the plan addresses it. Gaps found during this audit are marked **GAP** and resolved at the bottom.

## §2 User journey

| # | Requirement | Where |
|---|---|---|
| 1 | Sign up / log in, email + password | Roadmap Stage 3; Architecture §7 |
| 2 | Paste note into text area, submit | Stage 4 — `NoteForm` |
| 3 | Backend sends to Gemini, gets structured analysis | Architecture §5; Stage 5 + 8 |
| 4 | UI shows conditions, evidence, doc quality, code | Stage 6 — `ConditionCard` |
| 5 | Edit or reject any extracted item | Stage 7 — `ConditionEditor` |
| 6 | Reviewed analysis saved; history with corrections preserved | Data model §1–2; Stage 7 |
| 7 | Public URL | Deployment §1, §6 |

## §3.1 Authentication

| Requirement | Where |
|---|---|
| Email + password, Firebase Auth | Stage 3 |
| User sees only their own notes — hard requirement | Security §3; `tests/security/test_tenant_isolation.py` |
| Unauthenticated → login screen | `ProtectedRoute`, Stage 3 |
| Unauthenticated API requests rejected | Security §2 — route-enumeration test |
| Backend verifies token, does not trust client user ID | Security §2; Data model §3 — `owner_uid` never in a request schema, `extra="forbid"` |

## §3.2 Note submission

| Requirement | Where |
|---|---|
| Form accepting plain text, 100–3000 words | API contract §3 — **GAP 1** |
| Optional pseudonym + visit date | `CreateNoteRequest` |
| No real patient identifiers anywhere | Security §8 |
| Clear loading / success / error states | Stage 6; Architecture §7 state machines |

## §3.3 AI analysis

| Requirement | Where |
|---|---|
| Condition name | `Condition.name` |
| Verbatim evidence quote | `Condition.evidence_quote` |
| Documentation status | `documentation_status` enum — three values matching the PDF's examples |
| Suggested ICD-10 code | `icd10_code` |
| Confidence score | `confidence` |
| Documentation gaps list | `AnalysisOutput.documentation_gaps` |
| Overall summary | `AnalysisOutput.summary` |
| Schema-validated before DB or UI | Architecture §5 steps 3–4 |
| No regex / string-splitting parsing | `responseMimeType=application/json` + `responseSchema` + Pydantic |
| Evidence traceable; system notices invented quotes | `agent/validators/evidence.py`; Roadmap Stage 5 |
| Deliberate handling of malformed output | `agent/validators/output.py`; failure persisted as `invalid_output` |

## §3.4 Human review

| Requirement | Where |
|---|---|
| Edit any extracted field | `ReviewedCondition` carries all editable fields |
| Mark a condition incorrect | `action: "rejected"` + required `rejection_reason` |
| Add a condition the model missed | `action: "added"`, `origin: "human"` |
| Original AI output preserved alongside human version | Data model §1 — analyses immutable, reviews never copy AI values |
| Answer "what did the model say, what did the human change?" | Diff on `condition_id`; `ReviewDiff` component |

## §3.5 History

| Requirement | Where |
|---|---|
| Previous notes, most recent first | `notes: owner_uid ASC, created_at DESC` |
| Showing date, pseudonym, condition count, review status | `NoteSummary` — all four fields |
| Clicking opens full analysis | `NoteDetailPage` |

## §4.1 Frontend

| Requirement | Where |
|---|---|
| React + TypeScript | Stage 0 |
| `any` is not a type | eslint `no-explicit-any: error`, `tsconfig` strict |
| Any styling approach; clarity over animation | **GAP 2** |
| Component structure legible to a first-time reader | Folder structure — `components/` grouped by domain |

## §4.2 Backend

| Requirement | Where |
|---|---|
| Python, FastAPI | Stage 0 |
| Gemini key server-side only | Security §1 — grep verification before submission |
| Validate all input at API boundary | API contract §1; Security §4 |
| Explicit typed contract both sides | `api/schemas/` ↔ `types/api.ts` |

## §4.3 Data model

| Requirement | Where |
|---|---|
| Designed and documented before writing | This plan, before any code |
| User / Note / Analysis / Review are distinct | Data model §1 |
| Same note analyzed twice — does the old one disappear? | Data model §4 — explicitly answered: no, and why |
| Which fields machine / human / system | Data model §3 |
| "All notes for user X, newest first" efficiently | Data model §5 — index + cursor pagination |
| Choose a DB and justify it | Data model §0 — including what we give up |

## §4.4 Deployment

| Requirement | Where |
|---|---|
| Public URL, nothing run locally | Deployment §1 |
| FE on Vercel, BE on Render | Deployment §1 |
| Free-tier friendly and actually online | Deployment §1 — Render chosen over Cloud Run for the no-card reason |
| Working test account or self sign-up | Deployment §7 — both |

## §5 Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Public URL | Deployment §6 |
| 2 | Git repo with real commit history | Roadmap — ~28 scoped commits across 10 stages |
| 3a | README: local run from zero | Stage 9 |
| 3b | README: data model explained | Doc 02, condensed into README |
| 3c | README: 3–4 design decisions + alternatives | **GAP 3** — candidates below |
| 3d | README: next week's work + knowingly unfinished | **GAP 3** |
| 3e | README: how long it took, honestly | **GAP 3** |
| 4 | Prompts in the repo, findable | `backend/src/agent/prompts/v1_note_analysis.md` |
| 5 | 2–3 synthetic sample notes | `docs/sample-notes/` — three |

## §7 Bonus

| Bonus | Decision |
|---|---|
| Streaming | Cut — complicates validate-then-persist, which carries more marks |
| Caching identical notes | **In** — cache on `(content_hash, prompt_version, model_id)` |
| Inline evidence highlighting | **In** — nearly free once match offsets are persisted |
| Tests on schema validation + failure paths | **In** — the core of the test plan |
| Metrics view | Cut first if time runs short |
| PDF/image upload | Cut |
| Rate limiting per user | **In** — 10/hour per UID |

## §8 Ground rules

| Rule | Where |
|---|---|
| AI assistants allowed, must be defensible | Every decision in this plan has a stated alternative and reason |
| Never real patient data | Security §8 |
| Free tiers only | Deployment §1 |
| If stuck, write it down | **GAP 4** |
| Cut features not quality, and say what you cut | Roadmap — explicit cut order |

---

# Gaps found in this audit, and how they are resolved

### GAP 1 — Word count floor — RESOLVED: enforce the document literally
The PDF says "plain text, expect 100–3000 words". My API contract had set the minimum at 1 word.

**Resolution: both bounds are hard.** `content` must be 100–3000 words, plus a 40,000-character ceiling (a single 40,000-character "word" would otherwise pass a word-count-only check). Outside the range is a 422 naming the actual count and the accepted range.

The frontend counts words live, displays `n / 100 minimum` below the floor and `n / 3000` above it, and keeps submit disabled until the count is valid — the boundary is visible while typing rather than discovered by a rejected request. The three sample notes in `docs/sample-notes/` are each written to sit comfortably inside 100–3000 words so a reviewer can paste any of them and have it accepted.

### GAP 2 — Styling approach unspecified
**Resolution:** plain **CSS Modules** with a small design-token file (colour, spacing, type scale). No Tailwind, no CSS-in-JS runtime, no component library. Rationale for the README: the brief values information hierarchy over polish, and a dependency-free approach keeps the bundle small and the components readable to a first-time reader. Three visual priorities: documentation status must be scannable at a glance, unverified evidence must be impossible to miss, and AI-vs-human differences must be visible without clicking.

### GAP 3 — README sections not itemized in the roadmap
**Resolution:** Stage 9 now specifies the required README sections explicitly. The four design decisions to be written up:
1. No client-side Firestore — one enforcement point vs. two policy engines.
2. Note creation separate from analysis — the note survives a provider outage.
3. Reviews do not copy AI values — the diff is computed, so there is no stale copy.
4. Firestore over Postgres — with an honest statement of what it costs us.

Plus: what I'd build next with one more week, what I knowingly left unfinished, and hours spent — logged per stage as I go, not reconstructed at the end.

### GAP 4 — No "what I got stuck on" section planned
**Resolution:** the README gets a **Known Limitations and Open Problems** section, written as I go rather than at the end. Already-known entries: in-process rate limiter and key pool break across multiple instances; hand-mirrored TypeScript types will drift without OpenAPI generation; fuzzy evidence matching has a tunable threshold I will not have enough real data to tune well; Render cold starts; no `org_id` for multi-user clinics.
