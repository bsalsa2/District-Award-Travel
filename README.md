# District Award Travel — Platform

Travel savings service: we find award redemptions worth more than cash, document them, and charge 10% of verified savings.

---

## Architecture

```
platform/public/
  index.html      — public landing page (proof strip, FAQ, sample plan)
  intake.html     — client intake form
  client.html     — client portal (SSE-driven, no polling in background tabs)
  admin.html      — operator dashboard (kanban, cockpit, savings ledger)

backend/
  main.py         — FastAPI app, all endpoints, SQLAlchemy models
  ai_client.py    — AI provider abstraction (circuit breaker, usage logging)
  tests/          — 83 tests (pytest)

scripts/
  seed_staging.py — TEST-prefixed fake data, refuses to run in production
  load_test.py    — asyncio/httpx load test (50 portal sessions + 1 admin)

.github/workflows/
  nightly-backup.yml — pg_dump -> AES-256 encrypt -> 7-day GH Actions artifact
```

**Database:** PostgreSQL (Render). SQLite for local dev. Additive migrations via `Base.metadata.create_all()` plus `_INDEX_MIGRATIONS` list executed at startup.

**Auth:** JWT (HS256, 7-day TTL). Admin token in localStorage. Client token in sessionStorage. `require_admin` / `current_identity` FastAPI dependencies.

---

## Environment variables

| Variable | Required | How to generate | Notes |
|---|---|---|---|
| `SECRET_KEY` | Yes (prod) | `openssl rand -hex 32` | All sessions invalidate on change |
| `ADMIN_PASSWORD` | Yes (prod) | Your choice | Startup re-syncs admin row; changing re-hashes |
| `DATABASE_URL` | Yes (prod) | Render -> dat-db -> External URL | Presence triggers production mode |
| `ENV` | No | `production` / `staging` / `development` | Defaults: production if DATABASE_URL set, else development |
| `ALLOWED_ORIGINS` | No | `https://district-award-travel.onrender.com` | Comma-separated; defaults to Render URL |
| `GMAIL_USER` | No | Your Gmail address | Required for email; app degrades silently without it |
| `GMAIL_APP_PASSWORD` | No | Google Account -> Security -> App passwords | 16-char app password, not account password |
| `GROQ_API_KEY` | No | console.groq.com | Document scanning AI |
| `GEMINI_API_KEY` | No | aistudio.google.com | Sweet spots + option research AI |
| `PROOF_MIN_SAVINGS_CENTS` | No | Default: 500000 ($5k) | Public proof strip threshold |
| `PROOF_MIN_TRIPS` | No | Default: 5 | Public proof strip threshold |
| `PROOF_MIN_CPP_RECORDS` | No | Default: 3 | Public proof strip threshold |
| `SLOW_QUERY_MS` | No | Default: 200 | Log queries slower than this |
| `CRON_SECRET` | No | `openssl rand -hex 20` | Protects `/api/cron/digest` |
| `SENTRY_DSN` | No | sentry.io project | Error reporting; no-op when unset |
| `PROD_DATABASE_URL` | GitHub secret | Same as DATABASE_URL | Nightly backup workflow |
| `BACKUP_PASSPHRASE` | GitHub secret | `openssl rand -base64 32` | AES-256 backup key; keep an offline copy |

---

## Local development

```bash
# 1. Clone and install
git clone https://github.com/bsalsa2/district-award-travel.git
cd district-award-travel
pip install -r backend/requirements.txt

# 2. Run (SQLite, ephemeral SECRET_KEY -- dev only)
uvicorn backend.main:app --reload --port 8000

# 3. Open
open http://localhost:8000          # landing page
open http://localhost:8000/admin    # admin (password: dat2026 in dev)
```

No `.env` file needed for local dev -- the app generates ephemeral keys when env vars are absent and `DATABASE_URL` is not set.

To use a local `.env`:
```bash
cp .env.example .env
# fill in values, then:
export $(cat .env | xargs) && uvicorn backend.main:app --reload
```

---

## Tests

```bash
pip install pytest httpx
python3 -m pytest backend/tests/ -v
# 83 tests, ~4s
```

---

## Deploy (Render)

The `render.yaml` defines:
- `dat` -- web service (Python, `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`)
- `dat-db` -- Postgres (free tier; **check expiry date in dashboard**)
- `dat-staging` + `dat-db-staging` -- staging copies

**First deploy:**
1. Render dashboard -> "New Blueprint" -> point at this repo -> `render.yaml` auto-detected.
2. After creation, set the `sync: false` env vars manually (Render won't touch them):
   - `SECRET_KEY` (`openssl rand -hex 32`)
   - `ADMIN_PASSWORD` (your password)
   - `GMAIL_USER` + `GMAIL_APP_PASSWORD` (for email)
3. Add GitHub repo secrets for nightly backups:
   - `PROD_DATABASE_URL` -- Render -> dat-db -> External Database URL
   - `BACKUP_PASSPHRASE` -- `openssl rand -base64 32` (store offline!)
4. Hit `https://district-award-travel.onrender.com/healthz` -- should return `{"status":"ok",...}`.

**Subsequent deploys:** push to `main`. Render auto-deploys. The old instance serves until the new one passes `/healthz`.

---

## Nightly backups

`.github/workflows/nightly-backup.yml` runs at 07:30 UTC. Manual run: Actions tab -> "Nightly encrypted DB backup" -> "Run workflow".

Artifacts kept 7 days. Restore procedure: see `RUNBOOK.md`.

---

## Cron digest

The admin "Today" panel populates from `GET /api/admin/digest`. To get the 7 AM daily digest email:

1. Create a free job at cron-job.org (or use GitHub Actions schedule).
2. `POST https://district-award-travel.onrender.com/api/cron/digest` with header `X-Cron-Secret: <your CRON_SECRET>`.
3. Set `CRON_SECRET` in Render env to the same value.

---

## Uptime monitoring

Sign up at uptimerobot.com (free). Monitor: `https://district-award-travel.onrender.com/healthz`, HTTP keyword `"ok"`, interval 5 minutes. Alert email: yours. This also provides modest keep-alive for the free tier.
