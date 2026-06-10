# DECISIONS.md — judgment calls log

Format: date · decision · reasoning. The bar for every change: closes more
intakes, fulfills faster, proves savings better, or protects client data.

---

## 2026-06-09 — Phase 0 (security)

- **Deleted `/api/setup/*` endpoints instead of authenticating them.** Startup
  `seed_admin()` already creates/re-syncs the admin from env vars on every boot,
  so the endpoints were pure attack surface with zero remaining purpose.
  Consequence: if login ever breaks, fix the env vars in Render and redeploy —
  there is deliberately no in-app backdoor anymore.
- **Deleted `/api/intake-create-client` entirely** rather than securing it. The
  product flow is now intake → admin reviews → Accept creates the account. An
  endpoint that mints accounts + passwords without auth contradicts that flow.
- **Production = `DATABASE_URL` is set.** Simple, zero-config heuristic for
  Render vs local. Local dev gets an ephemeral SECRET_KEY (sessions don't
  survive restarts in dev — acceptable).
- **Kept admin token in localStorage** (vs sessionStorage/cookies). Single
  operator who asked specifically not to be logged out on refresh. Logged as
  accepted risk in SECURITY.md.
- **Removed EmailJS rather than proxying it.** The backend already sends both
  intake emails over Gmail SMTP; the EmailJS call was a redundant duplicate
  with a publicly exposed key. One mail path = fewer failure modes.
- **Intake validation is a hand-rolled dict validator, not a Pydantic model.**
  The form posts dynamic keys (`trip3_dest`, `pts_united`, …); a rigid model
  would silently drop them. Cap-everything approach preserves flexibility.

---

## 2026-06-10 — Phase 2 (fulfillment engine)

- **Trips promoted to `trip_requests` table; `clients.data.trips` JSON array untouched.**
  The JSON blob can't power a kanban board, SLA timers, or append-only event history —
  all require stable IDs. Keeping the client-portal JSON means zero client-facing change
  and no refactor of the existing client endpoints. New trips written to both paths going
  forward; legacy trips importable via `/api/admin/trips/import-legacy`.

- **Backward transitions allowed one step** (e.g. `awaiting_decision → researching` when a
  client requests new options). Fully blocking backward moves would force a void+recreate
  dance for a common real-world event. The `workflow_events` audit trail captures every
  transition regardless.

- **Daily digest via external cron, not in-process scheduler.** Render free tier spins down
  idle services; an in-process `asyncio` loop or APScheduler would silently miss the 7 AM
  window after any spin-down. Solution: `POST /api/cron/digest?key=CRON_SECRET` endpoint
  (HMAC-protected) pointed at cron-job.org or a GitHub Actions schedule. Zero new
  dependencies; the `GET /api/admin/digest` endpoint powers the Today panel independently.
  Setup documented in README.

- **Manual time tracking (start/stop + "+15 min" quick-add) instead of auto-tracking.**
  Auto-tracking browser focus time is unreliable across tabs/devices and has privacy
  implications with clients present. Explicit operator input is more accurate for the
  effective-hourly-rate metric, which is the only place the data is used.

- **AI circuit breaker state stored in-process memory** (not DB). A dyno restart is itself
  a reasonable reset of "is the provider down?" — the breaker protects against cascading
  failures within a session, not across deployments. Simpler, zero overhead, no stale state.

- **Message templates stored in DB** (not hardcoded in JS). Operator can edit them in the
  UI without a code deploy. Six defaults seeded at first boot when the table is empty.
