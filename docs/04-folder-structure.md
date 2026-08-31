# Note Insight — Folder Structure

Refined from the reference structure. Deviations are marked **[changed]** with the reason.

```
note-insight/
├── README.md
├── .gitignore
├── .env.example                      # backend env template
├── docs/
│   ├── 01-architecture.md
│   ├── 02-data-model.md
│   ├── 03-api-contract.md
│   ├── 04-folder-structure.md
│   ├── 05-deployment.md
│   ├── 06-security-checklist.md
│   ├── 07-roadmap.md
│   └── sample-notes/                 # 3 synthetic notes, deliverable #5
│       ├── 01-diabetes-ambiguous.md
│       ├── 02-chf-well-documented.md
│       └── 03-polypharmacy-gaps.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt              # pinned, runtime only
│   ├── requirements-dev.txt          # pytest, ruff, mypy
│   ├── pyproject.toml                # ruff + mypy + pytest config
│   ├── firestore.indexes.json        # composite indexes, deployed not discovered
│   ├── firestore.rules               # deny-all for client SDKs
│   ├── src/
│   │   ├── main.py                   # app factory, middleware, router mounting only
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── health.py
│   │   │   │   ├── users.py
│   │   │   │   ├── notes.py
│   │   │   │   ├── analyses.py
│   │   │   │   └── reviews.py
│   │   │   ├── schemas/
│   │   │   │   ├── common.py         # error envelope, pagination
│   │   │   │   ├── user.py
│   │   │   │   ├── note.py
│   │   │   │   ├── analysis.py
│   │   │   │   └── review.py
│   │   │   └── dependencies/
│   │   │       ├── auth.py           # get_current_user -> AuthenticatedUser
│   │   │       ├── services.py       # service construction / injection
│   │   │       └── rate_limit.py
│   │   ├── agent/
│   │   │   ├── providers/            # [changed] was flat; providers need a namespace
│   │   │   │   ├── base.py           # LLMProvider protocol, ProviderRequest/Result
│   │   │   │   ├── gemini.py
│   │   │   │   ├── key_pool.py       # primary/fallback rotation
│   │   │   │   └── mock.py           # development provider, zero quota cost
│   │   │   ├── prompts/
│   │   │   │   ├── registry.py       # version -> prompt, cached
│   │   │   │   └── v1_note_analysis.md   # deliverable #4: the prompt, findable
│   │   │   ├── schemas/              # [changed] LLM contract != API contract
│   │   │   │   ├── raw_output.py     # Pydantic model of the model's JSON
│   │   │   │   └── response_schema.py# the JSON schema handed to Gemini
│   │   │   └── validators/
│   │   │       ├── evidence.py       # EvidenceVerifier
│   │   │       └── output.py         # parse + repair + validate
│   │   ├── services/
│   │   │   ├── auth/user_service.py
│   │   │   ├── notes/note_service.py
│   │   │   ├── analysis/analysis_service.py
│   │   │   └── review/review_service.py
│   │   ├── repositories/
│   │   │   ├── base.py               # Firestore client helpers, cursor encoding
│   │   │   ├── user_repository.py
│   │   │   ├── note_repository.py
│   │   │   ├── analysis_repository.py
│   │   │   └── review_repository.py
│   │   ├── models/                   # internal domain entities
│   │   │   ├── user.py
│   │   │   ├── note.py
│   │   │   ├── analysis.py
│   │   │   ├── review.py
│   │   │   └── enums.py
│   │   ├── core/
│   │   │   ├── config.py             # pydantic-settings Settings
│   │   │   ├── security.py           # Firebase token verification
│   │   │   ├── firebase.py           # [changed] Admin SDK init, isolated for testability
│   │   │   ├── logger.py             # structured JSON logging
│   │   │   ├── errors.py             # [changed] domain exception hierarchy
│   │   │   └── exception_handlers.py # [changed] domain error -> HTTP envelope
│   │   └── utils/
│   │       ├── hashing.py
│   │       ├── text.py               # normalization used by the evidence verifier
│   │       └── ids.py
│   └── tests/                        # [changed] moved under backend/
│       ├── conftest.py
│       ├── unit/
│       │   ├── test_evidence_verifier.py
│       │   ├── test_output_validator.py
│       │   ├── test_key_pool.py
│       │   └── test_review_invariants.py
│       ├── api/
│       │   ├── test_notes_api.py
│       │   ├── test_analyses_api.py
│       │   └── test_reviews_api.py
│       └── security/
│           └── test_tenant_isolation.py
│
└── frontend/
    ├── package.json                  # pinned versions
    ├── tsconfig.json                 # strict: true, noUncheckedIndexedAccess
    ├── vite.config.ts
    ├── .eslintrc.cjs                 # no-explicit-any: error
    ├── .env.example                  # VITE_ prefixed, public config only
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx                   # routes only
        ├── types/
        │   ├── api.ts                # mirror of backend response schemas
        │   └── domain.ts
        ├── config/env.ts             # [changed] parsed + validated env, no import.meta.env sprawl
        ├── lib/firebase.ts           # [changed] Auth SDK init only
        ├── contexts/AuthContext.tsx
        ├── services/
        │   ├── apiClient.ts          # the only fetch in the app
        │   ├── notesApi.ts
        │   ├── analysesApi.ts
        │   └── reviewsApi.ts
        ├── hooks/
        │   ├── useAuth.ts
        │   ├── useNoteHistory.ts
        │   ├── useNoteDetail.ts
        │   ├── useAnalyzeNote.ts
        │   └── useReviewDraft.ts     # the review editing state machine
        ├── layouts/AppLayout.tsx
        ├── pages/
        │   ├── LoginPage.tsx
        │   ├── NewNotePage.tsx
        │   ├── HistoryPage.tsx
        │   └── NoteDetailPage.tsx
        ├── components/
        │   ├── common/               # Button, Card, Badge, Spinner, ErrorState, EmptyState
        │   ├── auth/AuthForm.tsx, ProtectedRoute.tsx
        │   ├── notes/NoteForm.tsx, NoteHighlighter.tsx, NoteSummaryRow.tsx
        │   ├── analysis/ConditionCard.tsx, GapList.tsx, EvidenceBadge.tsx,
        │   │            ConfidenceMeter.tsx, AnalysisStatusBanner.tsx
        │   └── review/ConditionEditor.tsx, AddConditionForm.tsx, ReviewDiff.tsx
        ├── styles/
        └── utils/
```

## Deviations from the reference, and why

1. **`tests/` moved under `backend/`.** A root `tests/` implies one suite for two languages. Backend tests need `conftest.py` and the Python path rooted at `backend/`; frontend tests, if added, belong beside Vite. Keeping them separate keeps both toolchains simple.

2. **`agent/schemas/` added.** The reference has `agent/prompts/` and `agent/validators/` but nowhere for the LLM's own contract. That contract is *not* the API contract — the model does not assign `condition_id`, does not know about `owner_uid`, and its schema will drift as prompts evolve. Conflating the two would leak model-shaped fields into API responses.

3. **`agent/providers/` subfolder.** Four files (base, gemini, key pool, mock) that belong together.

4. **`core/errors.py` + `core/exception_handlers.py`.** Domain code raises domain exceptions with no knowledge of HTTP; one handler module translates them into the envelope. Without this split, services end up importing `HTTPException` and the layering claim becomes fiction.

5. **`core/firebase.py` separate from `core/security.py`.** SDK initialization is a process-lifecycle concern; token verification is a request concern. Splitting them makes verification unit-testable with a faked verifier.

6. **`frontend/src/config/env.ts` and `lib/firebase.ts`.** Environment access is parsed and validated in exactly one place, so a missing `VITE_FIREBASE_API_KEY` fails loudly at boot rather than as `undefined` inside the auth SDK.

7. **`requirements.txt` lives in `backend/`, not the root.** The root has no Python. A root-level requirements file that only applies to a subdirectory is the kind of small dishonesty that costs someone twenty minutes.

## File size discipline

No file over ~250 lines. `main.py` wires only. Routes are thin enough to read in one screen. If a service crosses 250 lines it is doing two jobs and gets split.
