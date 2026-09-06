# Note Insight — Completion Checklist

Every requirement in the brief, traced to where it is satisfied and how it was verified.

Legend: **DONE** verified working · **CUT** deliberate, documented

---

## 1. Authentication (brief §3.1)

| # | Requirement | Status | Where | Verified by |
|---|---|---|---|---|
| 1.1 | Email + password sign-up | DONE | `LoginPage.tsx`, `AuthContext.tsx` | Signed up live against Firebase Auth |
| 1.2 | Email + password sign-in | DONE | `AuthContext.signIn` | Live sign-in; user appears in console |
| 1.3 | Sign-out | DONE | `AppLayout.tsx` | Manual |
| 1.4 | Unauthenticated users get the login screen | DONE | `ProtectedRoute.tsx` | Manual — every route redirects |
| 1.5 | Unauthenticated API requests rejected | DONE | `dependencies/auth.py` | Live: every protected route → 401; `test_route_protection.py` |
| 1.6 | Backend verifies the identity token | DONE | `core/security.py` | Garbage token → 401; expired token → `TOKEN_EXPIRED` |
| 1.7 | `owner_uid` never trusted from the client | DONE | All services take it from the token | `test_owner_uid_cannot_be_supplied_in_the_payload` |
| 1.8 | A user only ever sees their own data | DONE | Owner-scoped repository queries | Live cross-tenant probe with a second real account, all 404; `test_tenant_isolation.py` |
| 1.9 | 404 rather than 403 on another user's resource | DONE | `ResourceNotFoundError` everywhere | Live; **fixed a 409 leak on review submit** |

## 2. Note submission (brief §3.2)

| # | Requirement | Status | Where | Verified by |
|---|---|---|---|---|
| 2.1 | Form accepting 100–3000 words | DONE | `NewNotePage.tsx`, `CreateNoteRequest` | Live 422 at 11 words and at 5000 words |
| 2.2 | Optional pseudonym + visit date | DONE | `schemas/note.py` | Live submission with and without |
| 2.3 | No real patient identifiers requested | DONE | Form asks for a pseudonym only | Manual review of every field label |
| 2.4 | Loading state | DONE | `useAsync.ts`, `Feedback.tsx` | Manual — ~5s call shows progress |
| 2.5 | Success state | DONE | Redirect to the note detail page | Manual |
| 2.6 | Error state that does not lie | DONE | `Feedback.tsx` with retry | Observed genuinely during the missing-index outage |
| 2.7 | Empty / whitespace note rejected | DONE | `content: min_length=1` | Live → 422 |
| 2.8 | Oversized body rejected | DONE | `BodySizeLimitMiddleware` | Live 200KB body → 413 |

## 3. AI analysis (brief §3.3)

| # | Requirement | Status | Where | Verified by |
|---|---|---|---|---|
| 3.1 | Conditions with name | DONE | `Condition.name` | Live: 6 conditions on sample 01 |
| 3.2 | Verbatim evidence quote | DONE | `Condition.evidence_quote` | Live |
| 3.3 | Documentation status | DONE | 3-value enum | Live: `ambiguous` / `well_documented` / `mentioned_without_plan` all produced |
| 3.4 | Suggested ICD-10 code | DONE | `Condition.icd10_code`, nullable | Live: E11.9, N18.3, I10, E78.5, G62.9, E66.9 |
| 3.5 | Confidence score | DONE | `Condition.confidence` 0.0–1.0 | Live |
| 3.6 | Documentation gaps, actionable | DONE | `DocumentationGap` | Live: 5 gaps on sample 01, 10 on sample 03 |
| 3.7 | Overall summary | DONE | `AnalysisOutput.summary` | Live |
| 3.8 | Schema-validated before DB or UI | DONE | `validators/output.py` + Pydantic | `test_output_validator.py` |
| 3.9 | No regex / string-split parsing | DONE | `response_schema` + `json.loads` | Code review |
| 3.10 | Evidence traceable to the note | DONE | `validators/evidence.py` | **Caught a real fabrication live**; 13/19 verified under v2 (6/6, 3/3, 4/10) |
| 3.11 | Malformed output handled deliberately | DONE | 4 failure codes, persisted | `test_output_validator.py`; hit live as `truncated` |

## 4. Human review (brief §3.4)

| # | Requirement | Status | Where | Verified by |
|---|---|---|---|---|
| 4.1 | Edit any extracted field | DONE | `ConditionEditor.tsx`, `useReviewDraft.ts` | Live: renamed a condition, changed its code |
| 4.2 | Mark a condition incorrect | DONE | `action: "rejected"` + reason | Live |
| 4.3 | Add a condition the model missed | DONE | `origin: "human"`, `action: "added"` | Live |
| 4.4 | Original AI output preserved | DONE | Analyses are never mutated | Live: model output and human version both readable after review |
| 4.5 | "What did the model say vs the human?" answerable | DONE | Diff computed on `condition_id` | `ReviewPanel.tsx` renders both sides |
| 4.6 | Review versioning | DONE | `version`, monotonic per analysis | Live: v1 and v2 both retained |
| 4.7 | Stale-analysis review rejected | DONE | 409 `REVIEW_CONFLICT` | `test_reviews_api.py` |

## 5. History (brief §3.5)

| # | Requirement | Status | Where | Verified by |
|---|---|---|---|---|
| 5.1 | Notes listed newest first | DONE | Composite index, `created_at DESC` | Live, correct order |
| 5.2 | Shows date, pseudonym, condition count, review status | DONE | `NoteSummaryResponse` | Live |
| 5.3 | Clicking opens the full analysis | DONE | `NoteDetailPage.tsx` | Live |
| 5.4 | Efficient owner-scoped query | DONE | One index, denormalized counters | No fan-out reads — code review |
| 5.5 | Cursor pagination | DONE | `(created_at, note_id)` cursor | Live page 2; bad cursor → 400 |

## 6. Technical requirements (brief §4)

| # | Requirement | Status | Verified by |
|---|---|---|---|
| 6.1 | React + TypeScript | DONE | `tsc --noEmit` clean |
| 6.2 | No `any` | DONE | `eslint no-explicit-any: error`, zero occurrences |
| 6.3 | Readable component structure | DONE | Grouped by feature under `components/` |
| 6.4 | Python backend (FastAPI) | DONE | — |
| 6.5 | **Gemini key never reaches the browser** | DONE | Key is server-only; grep of `frontend/` finds nothing |
| 6.6 | Input validated at the API boundary | DONE | Pydantic on every route |
| 6.7 | Typed contract on both sides | DONE | Pydantic ↔ `types/api.ts` (hand-mirrored — a known limitation) |
| 6.8 | Data model documented before written | DONE | `docs/02-data-model.md`, committed before the models |
| 6.9 | User / Note / Analysis / Review separated | DONE | Four collections |
| 6.10 | Re-analysis keeps the old analysis | DONE | Live: 3 analyses on one note, all retained |
| 6.11 | Machine / human / system fields documented | DONE | README + `docs/02` |
| 6.12 | Query + index strategy explained | DONE | README |
| 6.13 | Database choice justified | DONE | README decision 4 |

## 7. Robustness (brief §6)

| # | Case | Status | Verified by |
|---|---|---|---|
| 7.1 | LLM returns garbage | DONE | `invalid_output` persisted; tested |
| 7.2 | LLM output truncated | DONE | `truncated` code — **hit live and fixed** |
| 7.3 | LLM invents a quote | DONE | `not_found`, kept — **hit live** |
| 7.4 | Provider unavailable | DONE | 503 + retry; note already saved |
| 7.5 | Network / TLS failure | DONE | **Was a 500; fixed to 503** with a regression test |
| 7.6 | Slow network | DONE | 45s timeout → `ProviderUnavailableError` |
| 7.7 | Empty note | DONE | 422 |
| 7.8 | 5000-word note | DONE | 422 naming the count |
| 7.9 | Path to another user's data | DONE | None found; live probe + tests |
| 7.10 | Rate limiting per user | DONE | Token bucket, 10/hr with burst 3 |

## 8. Bonus (brief §7)

| # | Item | Status | Note |
|---|---|---|---|
| 8.1 | Caching identical notes | DONE | Content hash + prompt version + model id |
| 8.2 | Inline evidence highlighting | DONE | Driven by stored character offsets |
| 8.3 | Automated tests on validation and failure paths | DONE | 158 tests |
| 8.4 | Rate limiting per user | DONE | — |
| 8.5 | Streaming | CUT | Complicates validate-then-persist; documented |
| 8.6 | Correction metrics view | CUT | Data is all stored; only aggregation missing |
| 8.7 | PDF / image upload | CUT | Out of scope for the time budget |

## 9. Deliverables (brief §5)

| # | Item | Status |
|---|---|---|
| 9.1 | README: local setup from zero | DONE |
| 9.2 | README: data model explained | DONE |
| 9.3 | README: 4 design decisions with alternatives | DONE |
| 9.4 | README: what next / left unfinished | DONE |
| 9.5 | README: hours spent | DONE |
| 9.6 | README: problems hit and what was tried | DONE |
| 9.7 | Prompts in a findable file | DONE — `backend/src/agent/prompts/` |
| 9.8 | 3 synthetic sample notes | DONE — `docs/sample-notes/` |
| 9.9 | Incremental commit history | DONE — 45+ scoped commits |
| 9.10 | No secrets in the repo | DONE — `.env` gitignored; verified with `git check-ignore` |
| 9.11 | Public URL | DONE — https://note-insight-eight.vercel.app |
| 9.12 | Test account | DONE — reviewer@note-insight.demo, seeded with three analysed notes; self sign-up also open |

---

## Bugs found and fixed during end-to-end verification

Each was found by running the real system, not by reading the code.

| # | Bug | Impact | Fix |
|---|---|---|---|
| 1 | Empty `FIRESTORE_EMULATOR_HOST=` routed all traffic to `dns:///` | Firestore completely unreachable | Commented out; the client tests for presence, not value |
| 2 | Antivirus TLS interception broke gRPC and `requests` | No Firestore or Gemini access locally | Merged CA bundle; verification stays on |
| 3 | Thinking tokens consumed the output budget | JSON truncated mid-object | `thinking_budget=0`; 20.7s → 5s, 6037 → 2700 tokens |
| 4 | `google-genai` pinned at 0.5.0 | Predates thinking config | Upgraded to 2.20.0 |
| 5 | Routes read cached global settings, not injected ones | Tests silently called live Gemini; 38 failures | `get_request_settings` from app state |
| 6 | Transport errors escaped as HTTP 500 | Network blip looked like an application bug | Caught in the provider → 503 |
| 7 | Model assembled quotes from separate passages | 4 of 6 conditions flagged unverified on note 01 | Prompt v2 bans it explicitly; note 01 now 6/6. Note 03 still 4/10 — documented, not hidden |
| 8 | Prompt edited without a version bump | Cache would serve stale analyses | v1 retained, change shipped as v2 |
| 9 | Reviewing another user's analysis returned 409 | Leaked that the analysis existed | Now 404 `ANALYSIS_NOT_FOUND` |
| 10 | `cache_hit` was stored `False` and never updated | Could never be true — a field that lied | Now describes the response |
| 11 | `fetchCurrentUser` was never called | `users` collection stayed empty; dead code | Called on auth state change |

---

## Deployment (brief §4.4)

| # | Requirement | Status | Verified by |
|---|---|---|---|
| 10.1 | Reachable at a public URL | DONE | Frontend and API both answering |
| 10.2 | Frontend on Vercel | DONE | SPA rewrite verified — deep routes do not 404 |
| 10.3 | Backend on Render | DONE | Docker, free tier, no card required |
| 10.4 | Free-tier only | DONE | Vercel, Render, Firebase Spark, Gemini free tier |
| 10.5 | Working test account | DONE | `reviewer@note-insight.demo`, three notes seeded |
| 10.6 | Production hardening | DONE | `/docs` and `/openapi.json` return 404; CORS allows one origin |
| 10.7 | Full journey on production | DONE | Sign-up, note, analysis 6/6 verified, review, history, isolation all checked live |

## Defects found after deployment

| # | Bug | Impact | Fix |
|---|---|---|---|
| 12 | `pydantic` pinned below what `google-genai` requires | Container build failed with ResolutionImpossible | Pin aligned; verified by resolving from an empty state |
| 13 | `/openapi.json` served in production while `/docs` was disabled | The schema was public; hiding the UI hid nothing | Both governed by the same condition, with a test per environment |
| 14 | Cache hit returned the earlier note's analysis | New note stayed "not analyzed" while the API reported success | Reused findings now stored as a document belonging to the requesting note |
| 15 | Verifier reported a quote made of the note's own words as "not found" | Told the clinician the model may have invented a finding when it had not | Third status `assembled`, with guards so an invented tail or a dropped dose still fails |
