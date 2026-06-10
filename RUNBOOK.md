# RUNBOOK.md — operational procedures

When something is broken, start here. Commands are exact — copy/paste.

---

## INCIDENT: Site is down

1. **Check the health endpoint:** open `https://district-award-travel.onrender.com/healthz`
   - `{"status":"ok"...}` → app + DB fine. Problem is DNS/your network/a specific page. Check the exact URL the client used.
   - `503 {"status":"degraded"...}` → **database problem**, jump to step 3.
   - Timeout / Render error page → app down, continue.
2. **Render dashboard → district-award-travel → Logs.** Look at the last 50 lines:
   - `RuntimeError: Refusing to start: missing required env vars` → someone cleared an env var. Environment tab → restore `SECRET_KEY` / `ADMIN_PASSWORD` → Save (auto-redeploys).
   - Crash loop with a traceback → copy the traceback, roll back: Render → Deploys → previous good deploy → "Rollback to this deploy".
   - No instance at all → free instance may be suspended (free-hours exhausted). Dashboard shows the reason; wait for the monthly reset or upgrade.
   - Nothing wrong, just slow first request (~50s) → that's the free-tier cold start, not an outage.
3. **Database down:** Render dashboard → dat-db. If expired/deleted (free-tier 30/90-day policy): create a new Postgres, then follow **Database restore** below. If it shows errors, check Render's status page (status.render.com) before doing anything drastic.
4. After recovery, confirm: `/healthz` returns ok, log into admin, check the Money tab totals.

## INCIDENT: Client says they didn't get an email

1. Admin token in hand, query the email log:
   `GET /api/admin/email-log` (or check the admin UI if wired) — find the recipient.
   - `status: sent` → it left our server. Ask them to check spam; gmail-to-gmail usually lands. Consider the transactional-provider upgrade in COST.md if this recurs.
   - `status: failed` → read `last_error`:
     - `GMAIL_USER / GMAIL_APP_PASSWORD not set` → set them in Render env.
     - `Username and Password not accepted` → the Google App Password was revoked (changing the Google account password does this). Make a new one: Google Account → Security → 2-Step Verification → App passwords → update `GMAIL_APP_PASSWORD` in Render.
     - `quota` / rate errors → Gmail daily cap (~500). Wait, or upgrade provider (COST.md).
   - No row at all → the triggering action never ran; check `error_log` (`GET /api/admin/email-log` sibling) and Render logs for the request.
2. Resend manually: admin → message composer → resend, or use the template library.

## INCIDENT: Rotate a leaked key/secret

Order matters — rotate, then redeploy, then verify.

| Secret | Where | Rotation |
|---|---|---|
| `SECRET_KEY` | Render env | Generate `openssl rand -hex 32`, replace in Render → Save. **All sessions invalidate** (every client + you re-log-in). |
| `ADMIN_PASSWORD` | Render env | Replace in Render → Save. Startup re-syncs the admin row automatically. |
| `GMAIL_APP_PASSWORD` | Google + Render | Revoke in Google Account → App passwords; create new; update Render. |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | provider consoles + Render | Revoke in console, create new, update Render. AI features degrade gracefully meanwhile. |
| `BACKUP_PASSPHRASE` | GitHub repo secrets | New backups use the new passphrase; **keep the old one** until its 7-day artifacts age out or old backups become unreadable. |
| `PROD_DATABASE_URL` (GH secret) | Render + GitHub | Render → dat-db → rotate credentials if supported, else recreate DB user; update the GitHub secret. |
| `CRON_SECRET` | Render env + cron service | Update both ends. |

After any rotation: redeploy, hit `/healthz`, log in, send yourself a test message.

## INCIDENT: Render deploy failed

1. Render → Deploys → click the failed deploy → read the build/runtime log.
2. Common causes here:
   - `pip install` failure → a dependency pin broke; compare `backend/requirements.txt` against the last good deploy's diff.
   - `Refusing to start: missing required env vars` → env var got cleared; restore it.
   - Import/syntax error → the deploy shipped broken code. **Rollback first** (Deploys → previous good → Rollback), fix at leisure.
3. The app never auto-deploys broken code into traffic — Render keeps the old instance serving until the new one passes `/healthz`. A "failed deploy" usually means clients are STILL on the old version: don't panic, fix forward or roll back.

## INCIDENT: AI provider outage (Gemini/Groq down)

**Nothing to do.** This is handled in code: 20s timeouts, 2 retries, a 10-minute circuit breaker per provider, and every AI feature has a manual path (scanner → type balances manually; sweet spots → research cockpit checklist). The admin header dot shows red while a breaker is open; `GET /api/admin/ai-health` has details. If it's still red after an hour, check the provider's status page. Intake, messaging, plans, and the ledger never depend on AI.

## INCIDENT: Database restore needed

See the drilled procedure below.

---

## Database restore (DRILLED 2026-06-10 — this procedure is verified)

**Drill result:** seeded DB (5 clients, 5 savings records, 5 trips, 1 intake) →
dump → AES-256 encrypt → decrypt → restore to scratch DB → **row counts matched
exactly**. Timing at current data size: dump 0.1s, encrypt 0.3s, decrypt 0.2s,
restore 0.4s — **~1s total**, will grow with data but stays minutes, not hours.

### To restore production from a nightly backup

1. **Download the backup**: GitHub → repo → Actions → "Nightly encrypted DB backup"
   → pick the most recent successful run → download the `dat-db-backup-*` artifact.
   Unzip it to get `dat-backup-YYYY-MM-DD.dump.enc`.

2. **Decrypt** (needs `BACKUP_PASSPHRASE` — stored in GitHub repo secrets AND
   your offline copy):
   ```bash
   export BACKUP_PASSPHRASE='<the passphrase>'
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
     -in dat-backup-YYYY-MM-DD.dump.enc -out restored.dump \
     -pass env:BACKUP_PASSPHRASE
   ```

3. **Create the target database** — in Render: create a new Postgres instance
   (or use the existing one if it's intact but data is bad). Copy its
   **External Database URL**.

4. **Restore**:
   ```bash
   pg_restore --no-owner --no-privileges --clean --if-exists \
     -d 'postgres://USER:PASS@HOST/DBNAME' restored.dump
   ```
   (`--clean --if-exists` drops and recreates objects — safe on a fresh DB,
   destructive-by-design on a corrupted one.)

5. **Verify before pointing the app at it**:
   ```bash
   psql 'postgres://USER:PASS@HOST/DBNAME' -c \
     "SELECT (SELECT count(*) FROM clients) AS clients,
             (SELECT count(*) FROM savings_records) AS savings,
             (SELECT count(*) FROM trip_requests) AS trips,
             (SELECT count(*) FROM intakes) AS intakes;"
   ```
   Sanity-check the numbers against what you expect.

6. **Point the app**: Render dashboard → dat web service → Environment →
   set `DATABASE_URL` to the new External URL → save (triggers redeploy).

7. **Smoke test**: log into admin, check Money tab totals and client list.

### Backup system facts
- Schedule: nightly 07:30 UTC via `.github/workflows/nightly-backup.yml`
- Manual run: Actions tab → the workflow → "Run workflow"
- Retention: 7 days as GitHub Actions artifacts
- Encryption: AES-256-CBC, PBKDF2 200k iterations; plaintext never stored
- Each run round-trip-verifies the backup decrypts and parses (`pg_restore --list`)
- **Setup required once (YOU):** add repo secrets `PROD_DATABASE_URL` (Render
  External URL) and `BACKUP_PASSPHRASE` (`openssl rand -base64 32`; keep an
  offline copy — losing it makes all backups unreadable).
