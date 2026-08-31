# Note Insight — Architecture

## 1. Purpose

Note Insight turns a free-text clinical note into a reviewable, structured artifact: conditions with verbatim evidence, documentation-quality status, suggested ICD-10 codes, documentation gaps, and an encounter summary — with a human correction layer on top that never destroys what the model originally said.

The product's most durable asset is not the analysis. It is the **delta between the model's draft and the clinician's correction**. Every decision below is biased toward preserving that delta cleanly.

## 2. System shape

```
┌────────────────────────┐        ┌──────────────────────────────────────┐
│  React + TypeScript    │        │  FastAPI (Python 3.11, Docker)       │
│  Vite SPA              │        │                                      │
│                        │        │  api/routes   ── thin HTTP layer     │
│  Firebase Auth         │ HTTPS  │        │                             │
│  (client SDK:          ├───────►│  services     ── business rules      │
│   sign-in only)        │ Bearer │        │                             │
│                        │ IDtoken│  repositories ── persistence         │
│  No Firestore SDK      │        │        │                             │
│  No Gemini SDK         │        │  agent        ── LLM + guards        │
└────────────────────────┘        └────────┬─────────────┬───────────────┘
    Vercel / Firebase Hosting              │             │
                                   ┌───────▼──────┐ ┌────▼─────────────┐
                                   │  Firestore   │ │  Gemini API      │
                                   │ (Admin SDK)  │ │  (primary +      │
                                   │              │ │   fallback keys) │
                                   └──────────────┘ └──────────────────┘
                                            Render
```

## 3. The decision that shapes everything: no client-side Firestore

The browser gets the Firebase **Auth** SDK only. It never talks to Firestore directly. All reads and writes go through FastAPI using the Admin SDK.

**Alternative considered:** client-side Firestore with security rules (`request.auth.uid == resource.data.owner_uid`). That is the conventional Firebase shape and it is faster to build.

**Why rejected:** it creates two authorization implementations — rules for the browser path, Python for the API path — that must agree forever. The assessment states tenant isolation is a hard requirement, not a nice-to-have. One enforcement point, expressed as code we can unit-test, beats the latency we give up. Firestore rules are therefore set to **deny all client access**; the rules file is a backstop, not a parallel policy engine.

**Cost accepted:** no realtime listeners, and every read pays a Render hop. Fine at this product's scale (~25 notes per clinician per day).

## 4. Layers and their contracts

| Layer | Responsibility | Must not |
|---|---|---|
| `api/routes` | HTTP verbs, status codes, dependency wiring | Contain business rules or touch Firestore |
| `api/schemas` | Request/response models — the public contract | Leak internal storage field names |
| `api/dependencies` | Auth extraction, service construction, rate limiting | Do domain work |
| `services` | Orchestration, invariants, ownership checks, state transitions | Know about HTTP objects |
| `repositories` | Firestore document ↔ domain model mapping, queries, indexes | Know about Gemini or HTTP |
| `agent` | Prompt construction, provider calls, structured output, evidence verification | Know about Firestore or FastAPI |
| `models` | Internal domain entities | Depend on any outer layer |
| `core` | Config, logging, security, error types | Depend on anything above it |

Dependencies point inward only. `agent` and `repositories` are both leaves; `services` is the only layer permitted to combine them.

## 5. The analysis pipeline

```
note text
  │
  ▼ [1] AnalysisService.run()   cache lookup on (content_hash, prompt_version, model_id)
  │
  ▼ [2] LLMProvider.generate()  responseSchema + responseMimeType=application/json
  │                             timeout, bounded retry, key rotation on quota/auth failure
  ▼ [3] Pydantic validation     raw JSON → RawAnalysis
  │                             on failure: one repair attempt, then persist status=failed
  ▼ [4] EvidenceVerifier        every quote located in the source note (normalized match)
  │                             unverified quotes flagged, never silently dropped
  ▼ [5] AnalysisRepository      immutable document written on success AND on failure
  │
  ▼ [6] Typed response to the UI, including the verification report
```

Step 5 is deliberate. A failed analysis is still a row. "The model returned garbage at 14:02" is data worth keeping, and it is what lets the UI say something honest instead of spinning forever.

## 6. Provider abstraction

`agent/providers/base.py` defines one interface:

```python
class LLMProvider(Protocol):
    async def generate_analysis(self, request: ProviderRequest) -> ProviderResult: ...
```

`GeminiProvider` implements it. `MockProvider` implements it too, and the entire project is built against the mock until the final integration stage — this is how we honour the "do not burn Gemini quota" constraint. The active provider is chosen by `settings.llm_provider` and injected via `Depends`. Adding a second real provider later is one new file plus one config value; because `provider` and `model_id` are stored on every analysis, historical rows stay interpretable.

### Key rotation

`GeminiKeyPool` holds an ordered list from `GEMINI_API_KEYS` (comma-separated). On `429` / `RESOURCE_EXHAUSTED` / `401` / `403`, the current key is marked cooling-down and the call retries on the next key. Exhausting the pool raises `ProviderUnavailableError`, surfacing as HTTP 503 with a retry hint — not a 500. The pool is process-local state, which is correct for a single Render instance and documented as a known limitation for horizontal scaling.

## 7. Frontend architecture

- **Vite + React 18 + TypeScript strict.** `any` banned by lint rule (`@typescript-eslint/no-explicit-any: error`).
- `types/api.ts` mirrors the Pydantic response schemas — one reviewed file, so the typed contract is real on both sides.
- `services/apiClient.ts` is the only module that calls `fetch`. It attaches the Firebase ID token, retries once on 401 after a token refresh, and narrows the error envelope into a typed `ApiError`.
- `contexts/AuthContext.tsx` owns Firebase auth state. `hooks/` own request state machines (`idle | loading | success | error`) so no component invents its own.
- Components are presentational; pages compose hooks with components.

### Styling

**CSS Modules** with a small design-token file (colour, spacing, type scale). No Tailwind, no CSS-in-JS runtime, no component library. The brief values information hierarchy over polish, and a dependency-free approach keeps the bundle small and each component readable on its own. Three visual priorities, in order:

1. Documentation status is scannable at a glance across a list of conditions.
2. Unverified evidence is impossible to miss.
3. AI-vs-human differences are visible without clicking into anything.

## 8. Cross-cutting concerns

- **Request ID** — middleware assigns `X-Request-ID`, binds it into every log line, and returns it in every error body, so a reviewer's screenshot is traceable.
- **Structured logging** — JSON to stdout. Note content is **never** logged; only `note_id`, `content_hash`, word count, latency, and token usage.
- **Config** — a single `pydantic-settings` object, constructed once and injected. No `os.getenv` scattered through the codebase. Missing required settings fail at startup, not at request time.

## 9. Fit against stated future requirements

| Future requirement | Why it already fits |
|---|---|
| Multiple analyses per note | `analyses` is its own collection keyed by `note_id`; nothing is overwritten |
| A second AI provider | `LLMProvider` interface, plus `provider`/`model_id` recorded per analysis |
| Multiple users per clinic | `owner_uid` today; an `org_id` slots beside it and the repository filter becomes a two-field predicate |
| Prompt iteration | `prompt_version` stored on every analysis and included in the cache key |
| Correction metrics | `reviews` carry per-condition `action` and `origin`, queryable by `owner_uid` |
