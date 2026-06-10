# RUNBOOK.md — operational procedures

When something is broken, start here. Commands are exact — copy/paste.
(Expanded per-incident sections added in Phase 4 Step 7.)

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
