# INFRA_AUDIT.md — Infrastructure Audit & Remediation Plan

Audited: 2026-06-10 · Phases 1–3 merged · 73 tests passing
Scope: polling, backups, connection pooling, email path, secrets, indexes, risk ranking.

---

## 1. Current polling behavior (measured from code)

| Surface | What it polls | Interval | Visibility-aware? |
|---|---|---|---|
| Client portal (`client.html:327`) | `GET /api/client/me` (full payload incl. base64 screenshots in messages) | **every 10s** | No — polls in hidden tabs |
| Admin (`admin.html:2348`) | `loadClients()` + `loadIntakes()` (two requests) | **every 8s** | No |

Cost: one idle client tab ≈ 8,640 req/day; each request opens a DB session and
re-serializes the entire client JSON blob (which now contains base64 plan
screenshots — payloads can be hundreds of KB). Admin tab ≈ 21,600 req/day.
This is the single biggest load and Postgres-connection consumer in the system.

## 2. Database backup reality (Render)

- `render.yaml` provisions the **free** Postgres plan.
- **Render free Postgres has NO automated backups / point-in-time recovery.**
- Render's free databases also have an **expiry policy** (free instances are
  suspended/deleted after the free period — verify the exact date shown in
  your dashboard; this is a hard data-loss deadline, not a theoretical risk).
- Connection limit on free tier is small (~95 usable). Today's app fits, but
  see pooling below.
- **Current state: a single `DROP TABLE`, expired instance, or Render incident
  loses the entire client book and revenue ledger permanently.** This is the
  #1 risk in the system (flagged in SECURITY.md since Phase 0, still open).

## 3. Connection pool settings

`backend/main.py:111`:
```python
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
```
- SQLAlchemy defaults: `pool_size=5`, `max_overflow=10` → up to **15 connections**
  per process. Render free web service runs 1 instance → fine, but uvicorn with
  multiple workers would multiply this. No `pool_recycle` (Render closes idle
  connections; `pool_pre_ping` mitigates but recycle is cheaper). No explicit
  `pool_timeout`. **Verdict: acceptable, should be pinned explicitly.**

## 4. Email send path

- `send_email_to()` uses **synchronous `smtplib.SMTP_SSL`** inline in the
  request handler. Every intake submission performs **two blocking SMTP
  round-trips** (admin notify + client confirmation) before responding —
  each can take 2–10s and holds a worker + DB session the whole time.
- Failures are swallowed (`return False`) — good (no 500s) — but **silent**:
  no log table, no retry, no alert. "Client never got the email" is currently
  undiagnosable.
- Gmail SMTP limits: ~500 recipients/day (consumer), and Gmail increasingly
  spam-folders SMTP mail sent "from" a gmail.com address to strangers. Fine at
  current volume; a real risk as intake volume grows.

## 5. Secrets handling

- `render.yaml`: `SECRET_KEY` (generated), `ADMIN_PASSWORD`, `GMAIL_APP_PASSWORD`
  marked `sync: false` — **correct, not in git**.
- History scan (regex sweep for Google/Groq/AWS/GitHub/Slack key shapes over all
  151 commits): **no AI or cloud provider keys found**. ✅
- **One confirmed leak: EmailJS public key `d3KBln2jHflM1AYo5`** (+ service ID)
  in git history (removed from code in Phase 0, but history is forever).
  EmailJS public keys are low-sensitivity (client-side by design) but can be
  abused to burn your email quota. **Action: rotate/delete in EmailJS dashboard
  — already flagged in SECURITY.md, still on you.**
- Local dev fallbacks are safe (ephemeral SECRET_KEY, refuses to boot in prod
  without real secrets).

## 6. Index coverage

Indexed today: client/admin emails, `savings_records.client_id/status/report_token`,
`trip_requests.client_id/workflow_status`, `workflow_events.trip_id`,
`funnel_events.session_id/event/created_at`, `ai_usage.provider`, `intakes.email`.

**Missing (used by digest/pipeline/invoice queries):**
- `intakes.created_at` (digest 24h window)
- `savings_records.invoice_number` (`LIKE 'DAT-2026-%'` scan on every invoice assignment)
- `workflow_events.created_at` (digest 24h count)
- `trip_requests.savings_record_id` (cockpit joins)

All tables are tiny today; these cost nothing to add now and prevent
degradation later. FK columns exist but **SQLite dev won't enforce them and
no ON DELETE behavior is declared** — deleting a client currently orphans
savings/trip rows (admin delete endpoint exists!). Needs explicit handling.

## 7. Other findings

- **No request logging** — bare `print()` in email/AI paths only. A 500 in
  production is invisible unless you're watching Render logs live.
- **No health endpoint with DB check** — `/api/health` returns ok without
  touching the DB; a dead database looks "healthy" to any monitor.
- **Rate limiting** covers logins + intake only; `/api/track` has 120/h but
  `/api/public/proof`, `/api/public/examples`, `/api/report/{token}` are
  unthrottled (cheap queries, but scrapeable).
- **No gzip / cache headers** on static assets (admin.html is ~150KB+).
- **No staging environment** — every deploy tests in production on real PII.
- Render free web services **spin down after 15 min idle** → first request
  takes ~50s cold start; SSE connections also die on spin-down (relevant to
  Step 1 design).

---

## RANKED RISK LIST

| # | Risk | Likelihood | Impact | Verdict |
|---|---|---|---|---|
| 1 | **DB loss (no backups + free-tier expiry)** | Medium | Fatal — entire business | Fix first |
| 2 | **Silent failures** (no logging/alerting/health-with-DB) | High | High — you find out from clients | Fix second |
| 3 | **Blocking, unlogged email** in request path | High | Medium — lost intakes' confirmations, slow submits | Step 5 |
| 4 | 10s/8s polling × base64 payloads | Certain | Medium — connection/CPU pressure, slow portal | Step 1 |
| 5 | Client delete orphans ledger rows | Low | Medium — corrupt revenue history | Step 3 |
| 6 | EmailJS key in history (unrotated) | Low | Low | You: rotate |
| 7 | Missing indexes | Certain (later) | Low now | Step 3 |
| 8 | No staging / test-data separation | Medium | Medium | Step 4 |

---

## REMEDIATION PLAN (maps to your Steps 1–7)

- **Step 3 first (backups) — risk #1 outranks everything.** Nightly GitHub
  Actions `pg_dump`, encrypted with `age`/openssl AES-256 using a repo secret,
  stored as a GH Actions artifact (7-day retention), restore drill against a
  scratch SQLite→Postgres-compatible flow documented in RUNBOOK.md with timing.
  Plus indexes + safe ON DELETE handling (block client delete while ledger rows
  exist, rather than cascade-deleting revenue history).
- **Step 2 (observability):** JSON logging middleware (request_id/route/status/
  latency), first-party `error_log` + email-me-on-500 (Sentry optional via DSN,
  no-op when unset), `/healthz` doing `SELECT 1` + version, UptimeRobot setup
  documented. Recommendation: **do NOT keep-alive-ping to prevent spin-down**
  (burns free hours; cold starts are acceptable for a portal, and the uptime
  monitor's 5-min checks double as modest keep-alive anyway) — will log in
  DECISIONS.md.
- **Step 1 (SSE):** `/api/client/stream` SSE endpoint, 30s heartbeat, version
  counter on client data so the stream only pushes "something changed — refetch";
  auto-reconnect with backoff; fallback to 60s adaptive polling; Page Visibility
  pause for BOTH portal and admin. Connection math documented (each SSE conn
  holds no DB connection between events — checked via session-per-event design).
- **Step 5 (email):** single `queue_email()` interface using FastAPI
  `BackgroundTasks` + retry/backoff + `email_log` table; Gmail stays for now,
  provider swap is config-only; SPF/DKIM + Resend/Brevo recommendation in COST.md.
- **Step 4 (env separation):** `ENV` var (development/staging/production),
  `.env.example`, seed script with TEST-prefixed fake data that hard-exits when
  `ENV=production` or `DATABASE_URL` points at the prod host; staging service +
  DB defined in `render.yaml` (you click "create" in Render).
- **Step 6 (perf):** pin pool (`pool_size=5, max_overflow=5, pool_recycle=300`),
  GZipMiddleware, cache headers on static, rate limits on remaining public
  endpoints, locust load script + results recorded here.
- **Step 7 (runbook):** README rewrite, RUNBOOK.md (site down / restore / key
  rotation / email missing / failed deploy / AI outage), COST.md with ranked
  paid upgrades (#1: Render Starter Postgres for daily backups, ~$7/mo —
  cheap insurance for the irreplaceable ledger).

**Caveats I can't verify from inside the repo:** your actual Render dashboard
plan/expiry dates, UptimeRobot signup, EmailJS rotation, and DNS/domain access
for SPF/DKIM. Those four need your hands; everything else I can build and test.

---
*Checkpoint: awaiting approval before any changes.*
