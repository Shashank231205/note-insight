# Note Insight — Deployment Plan

All services on free tiers. Nothing in this build costs money.

## 1. Topology

| Component | Host | Free tier reality |
|---|---|---|
| Frontend (Vite static build) | **Vercel** | Generous; instant global CDN; preview deploys per branch |
| Backend (FastAPI, Docker) | **Render** Web Service | 512 MB, **spins down after 15 min idle** — cold start ~30–50 s |
| Database | **Firestore** Native mode | 50k reads / 20k writes per day |
| Auth | **Firebase Authentication** | Email/password, unlimited on Spark |
| LLM | **Gemini API** free tier | Rate-limited per key; two keys with rotation |

**Why Render over Cloud Run:** Cloud Run's free tier requires a billing account on file. The brief says nothing should cost money and to stop rather than pay — Render's free tier needs no card at all, which removes the risk entirely. Cloud Run would be the better production choice (faster cold starts, scale-to-zero without the 15-minute penalty) and the Dockerfile is portable to it unchanged.

**The cold start is the single biggest reviewer-experience risk in this deployment.** Mitigations, in order of honesty:
1. The frontend calls `GET /health` on app mount, so the backend is already waking while the reviewer types their password.
2. The login screen shows "connecting to server…" if health has not returned within 2 s — the UI never lies about what is happening.
3. The README states the cold start explicitly, with the expected duration. A reviewer who knows why the first request is slow reads it as engineering; one who does not reads it as a broken app.

## 2. Configuration

### Backend (Render environment variables — never in the repo)

```
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ALLOWED_ORIGINS=https://note-insight.vercel.app
FIREBASE_PROJECT_ID=note-insight-xxxx
FIREBASE_SERVICE_ACCOUNT_JSON=<the full service-account JSON, one line>
GEMINI_API_KEYS=<primary>,<fallback>
GEMINI_MODEL_ID=gemini-2.5-flash
LLM_PROVIDER=gemini
LLM_TIMEOUT_SECONDS=45
ANALYSIS_RATE_LIMIT_PER_HOUR=10
PROMPT_VERSION=v1
```

The service account arrives as a JSON **string in an env var**, parsed by `core/firebase.py`. No `service-account.json` file exists anywhere in the repo or the image — that file is in `.gitignore` and its absence is verified before every commit.

### Frontend (Vercel environment variables)

```
VITE_API_BASE_URL=https://note-insight-api.onrender.com
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_APP_ID=...
```

These are public by design — the Firebase web API key identifies the project, it does not authorize anything. That is why the Gemini key is nowhere near this list and never will be: it is a bearer credential for a paid API. A `VITE_`-prefixed variable is compiled into the bundle and readable by anyone with devtools.

## 3. Backend container

Multi-stage Dockerfile, `python:3.11-slim`, non-root user, `uvicorn` bound to `$PORT`. Health check on `/health`. No dev dependencies in the runtime image.

## 4. Firebase setup

1. Create the project; enable **Email/Password** in Authentication.
2. Create Firestore in **Native mode**, nearest region.
3. Deploy `firestore.rules` (deny-all for client SDKs) and `firestore.indexes.json` via the Firebase CLI. Both are in the repo and version-controlled; indexes are not left to be discovered from a runtime error.
4. Add the Vercel domain to Authentication → Settings → Authorized domains.
5. Create a service account with the **Cloud Datastore User** role only — not Editor. Least privilege, and it is a two-minute decision that a reviewer will notice.

## 5. CORS

`CORS_ALLOWED_ORIGINS` is an explicit allowlist read from config. `allow_origins=["*"]` never appears, including in development, where the value is `http://localhost:5173`.

## 6. Deploy order

1. Firebase project, Auth, Firestore, rules, indexes.
2. Backend to Render with `LLM_PROVIDER=mock` — verify auth, persistence, and the full journey with zero Gemini spend.
3. Frontend to Vercel against the live backend.
4. Set `CORS_ALLOWED_ORIGINS` to the real Vercel domain; redeploy backend.
5. Flip `LLM_PROVIDER=gemini`. Run the three sample notes once each. That is the intended total production Gemini spend for the whole assessment.

## 7. Test account

A seeded reviewer account (`reviewer@note-insight.demo`) with the three sample notes already analyzed and one of them reviewed — so the history page, the AI-vs-human diff, and the evidence highlighting are all visible without the reviewer having to wait on a cold start plus an LLM call before seeing anything. Self sign-up also works. Credentials go in the README and the submission email.

## 8. What is deliberately not deployed

No CI/CD pipeline, no staging environment, no monitoring stack. Vercel and Render both build on git push, which is enough for a five-day build, and pretending otherwise would be scope theatre.
