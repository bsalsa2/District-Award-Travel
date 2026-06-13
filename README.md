# District Award Travel — Platform

Award travel advisory service. We find redemptions worth more than cash, document the savings, and charge 10% of verified savings. Single operator (Braden), small client base.

---

## What this is

A FastAPI backend serving a set of static HTML pages. No frontend framework — HTML, vanilla JS, and inline CSS. The whole app ships as one Python file (`backend/main.py`) plus a `platform/public/` directory.

Revenue model: 10% of documented savings. We only earn when the client saves. The savings are computed from a cash benchmark (what the tickets would have cost), minus award taxes/fees, minus any other out-of-pocket costs. This is presented in a savings report, invoiced, and collected after booking.

---

## Architecture

```
backend/
  main.py           — FastAPI app: SQLAlchemy models, all API routes (~2,900 lines)
  ai_client.py      — AI provider abstraction (circuit breaker, usage logging)
  tests/            — pytest test suite (96 tests)

platform/public/
  index.html        — Public landing page (proof strip, fee calculator, intake CTA)
  intake.html       — 3-step intake wizard (client info → travel goals → points)
  client.html       — Client portal PWA (SSE-driven, boarding-pass trip cards)
  admin.html        — Operator dashboard (kanban, savings ledger, AI research tools)
  terms.html        — Terms of service
  privacy.html      — Privacy policy
  assets/           — PWA icons (192px, 512px, maskable, Apple touch)
  manifest.json     — PWA manifest

scripts/
  seed_staging.py   — TEST-prefixed fake data; refuses to run in production
  load_test.py      — asyncio/httpx load test (50 portal sessions + 1 admin)

.github/workflows/
  nightly-backup.yml — pg_dump → AES-256 encrypt → 7-day GitHub Actions artifact
```

**Database:** PostgreSQL on Render (prod). SQLite for local dev — no setup required. Schema migrations are additive: `Base.metadata.create_all()` creates new tables; `_INDEX_MIGRATIONS` at startup creates new indexes on existing tables.

**Auth:** JWT (HS256, 7-day TTL). Admin token in `localStorage`. Client token in `sessionStorage`. `require_admin` / `current_identity` FastAPI dependencies on every protected route.

**Real-time:** Server-Sent Events (`/api/client/stream`). The stream holds no DB connections between events. In-process `_client_versions` dict is bumped when admin writes to a client's data; the stream pushes a `changed` event within 2 seconds. Stream auto-closes after 5 minutes; the client reconnects. Falls back to 60-second polling after 3 consecutive SSE failures.

---

## Environment variables

Set all of these in the Render dashboard (Environment tab).

| Variable | Required | How to generate | Notes |
|---|---|---|---|
| `SECRET_KEY` | **Yes (prod)** | `openssl rand -hex 32` | All sessions invalidate on change |
| `ADMIN_PASSWORD` | **Yes (prod)** | Strong random password | Startup re-syncs admin row; changing it re-hashes |
| `DATABASE_URL` | **Yes (prod)** | Render → dat-db → External URL | Presence triggers production mode |
| `ENV` | No | `production` / `staging` / `development` | Defaults to `production` if `DATABASE_URL` is set |
| `ALLOWED_ORIGINS` | No | `https://district-award-travel.onrender.com` | Comma-separated; see SECURITY.md |
| `ADMIN_EMAIL` | No | Your admin email | Default: `admin@districtawardtravel.com` |
| `GMAIL_USER` | No | Your Gmail address | Required for email; app degrades silently without it |
| `GMAIL_APP_PASSWORD` | No | Google Account → Security → App passwords | 16-char app password, not account password |
| `NOTIFY_EMAIL` | No | Who gets intake notification emails | Defaults to `GMAIL_USER` |
| `GROQ_API_KEY` | No | console.groq.com | Email parsing |
| `GEMINI_API_KEY` | No | aistudio.google.com | Document scanning, sweet-spot analysis |
| `SEATS_AERO_API_KEY` | No | seats.aero | Live award availability search |
| `PROOF_MIN_SAVINGS_CENTS` | No | Default: `500000` ($5,000) | Public proof strip threshold |
| `PROOF_MIN_TRIPS` | No | Default: `5` | Public proof strip threshold |
| `PROOF_MIN_CPP_RECORDS` | No | Default: `3` | ¢/pt proof strip threshold |
| `CRON_SECRET` | No | `openssl rand -hex 20` | Protects `POST /api/cron/digest` |
| `SLOW_QUERY_MS` | No | Default: `200` | Log queries slower than this |
| `SENTRY_DSN` | No | sentry.io project | Error reporting; no-op when unset |
| `EMAIL_PROVIDER` | No | Default: `gmail` | Swap email transport without code changes |
| `PROD_DATABASE_URL` | GitHub secret | Same as `DATABASE_URL` | Used by nightly-backup workflow |
| `BACKUP_PASSPHRASE` | GitHub secret | `openssl rand -base64 32` | AES-256 backup encryption key — keep an offline copy |

---

## Local development

```bash
# 1. Clone and install
git clone https://github.com/bsalsa2/district-award-travel.git
cd district-award-travel
pip install -r requirements.txt

# 2. Run — uses SQLite automatically, no DB setup needed
#    An ephemeral SECRET_KEY is generated (tokens don't survive restarts in dev)
uvicorn backend.main:app --reload --port 8000

# 3. Open
open http://localhost:8000              # landing page
open http://localhost:8000/admin.html  # admin dashboard (password: dev-only-password)
open http://localhost:8000/client.html # client portal
open http://localhost:8000/intake.html # intake form
```

No `.env` file is needed for local dev. The app generates an ephemeral key and uses `dev-only-password` as the admin password when `DATABASE_URL` is not set.

To use a local `.env` file:
```bash
cp .env.example .env          # fill in values
export $(cat .env | xargs) && uvicorn backend.main:app --reload
```

---

## Running tests

```bash
pytest backend/tests/ -v
# 96 tests, ~4s
```

The test suite covers: savings formula correctness, workflow state machines, email retry logic, seed guard (staging vs production), funnel observability, AI client circuit breaker, digest computation, and public API response shapes.

---

## Deploy to Render

The `render.yaml` defines:
- `dat` — web service (Python, `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`)
- `dat-db` — Postgres (free tier; check expiry date in dashboard)
- `dat-staging` + `dat-db-staging` — staging copies

**First deploy:**
1. Render dashboard → "New Blueprint" → point at this repo → `render.yaml` is auto-detected
2. After creation, set the `sync: false` env vars manually (Render won't write them from `render.yaml`):
   - `SECRET_KEY` (`openssl rand -hex 32`)
   - `ADMIN_PASSWORD` (your password)
   - `GMAIL_USER` + `GMAIL_APP_PASSWORD` (for email notifications)
3. Add GitHub repository secrets for nightly backups:
   - `PROD_DATABASE_URL` — Render → dat-db → External Database URL
   - `BACKUP_PASSPHRASE` — `openssl rand -base64 32` (store this offline — losing it means losing the ability to restore encrypted backups)
4. Verify: `https://district-award-travel.onrender.com/healthz` should return `{"status":"ok",...}`

**Subsequent deploys:** push to `main`. Render auto-deploys. The old instance continues serving until the new one passes `/healthz`.

**Build command:** `pip install -r requirements.txt`  
**Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

## Nightly backups

`.github/workflows/nightly-backup.yml` runs at 07:30 UTC daily.

- `pg_dump` the production database
- AES-256 encrypt the dump using `BACKUP_PASSPHRASE`
- Upload as a GitHub Actions artifact (7-day retention)

Manual run: Actions tab → "Nightly encrypted DB backup" → "Run workflow".

Restore procedure: see `RUNBOOK.md`.

---

## Daily digest

The "Today" panel in the admin dashboard pulls from `GET /api/admin/digest`. To get a 7 AM email digest:

1. Create a free job at cron-job.org (or use a GitHub Actions schedule)
2. `POST https://district-award-travel.onrender.com/api/cron/digest` with header `X-Cron-Secret: <CRON_SECRET>`
3. Set `CRON_SECRET` in Render env to the same value

The endpoint is HMAC-protected (`hmac.compare_digest`) — a missing `CRON_SECRET` in Render returns 503.

---

## Uptime monitoring

UptimeRobot (free tier): monitor `https://district-award-travel.onrender.com/healthz`, HTTP keyword `"ok"`, 5-minute interval. This also provides modest keep-alive for the Render free tier, reducing cold starts.

Cold starts take ~50 seconds on the free tier. This is expected behavior — see `RUNBOOK.md` for the full cold-start runbook.

---

## Key design decisions

See `DECISIONS.md` for the full log. Short version:

- Integer cents throughout to prevent float rounding in revenue math
- JSON blob on the `clients.data` column for flexible portal schema without migrations
- SSE over WebSockets — unidirectional push is sufficient; no bidirectional protocol needed
- 10% fee model — we only earn when the client saves
- Boarding-pass card design — echoes the product domain

---

## Security

See `SECURITY.md` for the full audit and operator action items. The most time-sensitive item: **rotate the EmailJS API key** (it is in git history even though it has been removed from current code).
