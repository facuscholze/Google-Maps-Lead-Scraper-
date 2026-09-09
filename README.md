# AvaScho Lead Intelligence

B2B outbound-lead generation for small service businesses: find real companies
on Google Maps (official Places API only), audit their public websites, score
their fit as potential clients, and let a human approve personalized proposals
before any email is sent.

The pipeline is strict and sequential — nothing skips a phase and nothing is
sent without human approval:

```
Places → Lead → Website audit → Score → Opportunity → Proposal → HUMAN APPROVE → Send
```

## Product rules

- **Google Maps data** comes exclusively from the official **Places API
  (`searchText`)**. There is no scraping of Google Maps.
- **No invented data.** Emails are only recorded when found in public sources
  (website contact pages etc.); website problems are only reported with
  evidence. No canned sales copy — every proposal is generated from that
  lead's real audit data and must be reviewed/edited by a human.
- **Consent-first sending:** human approval (`APPROVED`) is required before an
  email is queued; an opt-out/suppression list (`DO_NOT_CONTACT`) is always
  checked; per-account daily limits, working hours and randomized delays are
  enforced by the queue.
- **Sensitive values live only in `backend/.env`** (JWT secret, Fernet
  `ENCRYPTION_KEY`, Google API keys, Gmail OAuth credentials). They are never
  committed, never sent to the browser.
- Tests run offline with **mocks only** (no live API/network calls).

## Repository layout

```
backend/    FastAPI + SQLAlchemy app (pipeline, scoring, proposals, queue)
├── alembic/                DB migrations (alembic upgrade head)
├── tests/                  pytest suite (offline, mocked providers)
├── app/                    api, models, repositories, services, integrations
├── requirements.txt
└── Dockerfile
frontend/   Next.js 15 (App Router) + Tailwind + TanStack Query UI
├── app/                    views: dashboard, searches, leads, proposals, settings
├── lib/                    typed API client (JWT in localStorage) + shared types
└── Dockerfile              standalone Next.js container
docker-compose.yml          db + backend + frontend local stack
```

## Quickstart

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 1) set SECRET_KEY (openssl rand -hex 32)
# 2) set ENCRYPTION_KEY:
#    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# 3) optional GOOGLE_MAPS_API_KEY (Places API). Without it the demo runs
#    fully offline with the mock provider.

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- A demo user is created automatically when `AUTO_CREATE_DEMO_USER=true`
  (`demo@avascho.com` / see `backend/.env`).

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

`next.config.mjs` rewrites `/api/*` to the backend
(`API_URL`, default `http://localhost:8000`), so the browser never calls the
backend cross-origin and no secret ever reaches the client.

### 3. Full stack with Docker

```bash
docker compose up --build
# frontend http://localhost:3000 · backend http://localhost:8000 · postgres :5432
```

`docker compose` loads `backend/.env` into the backend container (create it
from `backend/.env.example` first) and runs `alembic upgrade head` on startup.

## Email sending modes

| Mode | When | Behaviour |
| --- | --- | --- |
| Mock sender | `ALLOW_MOCK_EMAIL_SENDING=true` (default, demo) | Emails are queued and marked sent without leaving the machine |
| Real Gmail | `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` set + account connected in UI | OAuth 2.0 only; tokens encrypted at rest with `ENCRYPTION_KEY`; raw RFC-822 message sent via Gmail API |

Flow in the UI: **Proposal → Revisar/Editar → Aprobar → Elegir cuenta/horario →
Enviar**. The lead's email must exist with HIGH/MEDIUM confidence; LOW or
missing emails are never queued.

## Tests

```bash
cd backend
rm -f test_avascho.db    # the suite uses a local SQLite file; start clean
.venv/bin/python -m pytest tests/ -q     # 51 tests, mocks only, offline
```

Frontend type-check + production build:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

## Configuration cheat-sheet (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT signing |
| `ENCRYPTION_KEY` | Fernet key — encrypts stored OAuth tokens |
| `GOOGLE_MAPS_API_KEY` / `SEARCH_PROVIDER` | Places API `searchText` (or `mock`) |
| `GOOGLE_CLIENT_ID/SECRET` | Gmail OAuth for real sending |
| `ALLOW_MOCK_EMAIL_SENDING` | demo send path |
| `DAILY_EMAIL_LIMIT`, `MIN/MAX_SEND_DELAY_SECONDS`, `ALLOWED_HOURS_*`, `WORKING_DAYS` | outbound guardrails |
| `AI_PROVIDER` | `rule_based` (offline) or `openai_compatible` |
| `DATABASE_URL`, `REDIS_URL`, `EXECUTION_MODE` | infra (`inline` runs pipeline in-process) |
