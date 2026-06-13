# DECISIONS.md — judgment calls log

Format: date · decision · reasoning. The bar for every change: closes more intakes, fulfills faster, proves savings better, or protects client data.

---

## SQLite local dev / PostgreSQL prod
**Date**: 2026-06  
**Decision**: When `DATABASE_URL` is unset, the app uses SQLite (`dat.db` in the project root). When `DATABASE_URL` is present, it connects to Render Postgres.  
**Rationale**: Zero-config local start — `uvicorn backend.main:app --reload` just works with no external database. The `IS_PRODUCTION` flag gates strict secret enforcement; the local ephemeral `SECRET_KEY` avoids committing a dev secret.  
**Tradeoff**: A small subset of SQL behavior differs between SQLite and Postgres (some constraint semantics, JSON operators). Caught by keeping the test suite passing against SQLite in CI, and by smoke-testing on staging Postgres before merging significant schema changes.

---

## JWT over sessions
**Date**: 2026-06  
**Decision**: Authentication uses JWT (HS256) with a 7-day TTL rather than server-side sessions.  
**Rationale**: Stateless — no Redis or session store needed. Works on Render free tier out of the box. A single `SECRET_KEY` env var is the entire session infrastructure.  
**Tradeoff**: No server-side revocation of individual tokens. A stolen token is valid until it expires or `SECRET_KEY` is rotated. Mitigated by the 7-day TTL and the fact that rotating the key immediately invalidates all tokens across the system.

---

## Client token in sessionStorage
**Date**: 2026-06  
**Decision**: Client portal stores its JWT in `sessionStorage`, which is cleared when the browser tab closes.  
**Rationale**: Clients access the portal infrequently (checking trip status, viewing options). Session-scoped auth is a meaningful security improvement with minimal UX cost for this access pattern.  
**Tradeoff**: Clients must log in again on every new tab or browser session. Acceptable given infrequent use; less acceptable if clients needed the portal open constantly.

---

## Admin token in localStorage
**Date**: 2026-06  
**Decision**: Admin dashboard stores its JWT in `localStorage`, surviving page refreshes and browser restarts.  
**Rationale**: Single operator who works in the admin dashboard for extended sessions asked not to be logged out on refresh. The UX cost of re-login for the operator is high compared to a client checking in once a week.  
**Tradeoff**: An XSS vulnerability on the admin page could read `localStorage` and exfiltrate the token. Mitigated by locked CORS, `esc()` applied to every interpolation, and single-operator use. Documented in SECURITY.md. Revisit if a second admin is added.

---

## Integer cents everywhere
**Date**: 2026-06  
**Decision**: All monetary values are stored and computed as integer cents (or basis points for fee rates). No floats in financial math.  
**Rationale**: Float arithmetic produces rounding errors that compound across invoice calculations and aggregate stats. `calc_fee` uses integer arithmetic with explicit round-half-up: `(gross * rate + 5000) // 10000`. `calc_cpp_tenths` returns cents-per-point × 10 as an integer to preserve one decimal place without floats.  
**Tradeoff**: More verbose column names (`cash_benchmark_cents`, `fee_rate_bps`) and display formatting code (`$abs(c) // 100:,.{abs(c) % 100:02d}`). Worth it: incorrect money math would undermine the entire revenue model.

---

## Client data column as JSON blob
**Date**: 2026-06  
**Decision**: The `clients.data` column stores trips, messages, points balances, and savings as a JSON text blob rather than normalized tables.  
**Rationale**: Flexible schema accommodates evolving fields (new loyalty programs, message types, trip attributes) without database migrations. The client portal reads and writes this blob atomically. Fast to ship initially.  
**Tradeoff**: No SQL queries on nested data — can't `WHERE data->>'trips' = ...` portably. Not needed yet: the only consumer is the client portal, which reads the whole blob. When structured queries are needed (kanban, SLA tracking), data gets promoted to its own table (as `trip_requests` was in Phase 2). The blob remains for client-portal-specific fields that don't need querying.

---

## SSE over WebSockets for real-time
**Date**: 2026-06  
**Decision**: The client portal uses Server-Sent Events for push updates rather than WebSockets.  
**Rationale**: SSE is unidirectional (server → client), which is exactly what the use case requires: "notify the client that their data changed." It works over HTTP/1.1, has built-in reconnect in the browser, and requires no protocol upgrade or additional infrastructure. A `StreamingResponse` in FastAPI is sufficient.  
**Tradeoff**: Client-to-server messages (e.g. a client acknowledging a notification) use normal HTTP POST. No bidirectional real-time protocol. WebSockets would add complexity and a persistent connection for no benefit at this scale.

---

## Adaptive SSE with backoff on hidden tabs
**Date**: 2026-06  
**Decision**: The SSE stream auto-closes after 5 minutes and the client reconnects. On hidden tabs, the client falls back to 60-second polling after 3 consecutive SSE failures.  
**Rationale**: Render free tier spins down idle services. An always-on SSE connection fights spin-down and holds a server-side generator indefinitely. The 5-minute cap lets the service spin down naturally. In-process `_client_versions` dict means the stream holds no DB connections between events — the Postgres connection pool is unaffected by N idle portal tabs.  
**Tradeoff**: Slight latency on change notification (up to 2 seconds for the poll interval inside `gen()`). A user who has had the portal open for 5 minutes and admin sends an update will see it within 2 seconds; after reconnect, within 2 seconds of the new connection establishing. Acceptable.

---

## Message templates in DB
**Date**: 2026-06  
**Decision**: Message templates (subject + body with `{variable}` placeholders) are stored in the `message_templates` table, seeded with defaults at first boot, and editable via the admin UI.  
**Rationale**: Operator can edit wording, add templates, and adjust subject lines without a code deploy. Six defaults seeded when the table is empty. The `render_template` function substitutes `{first_name}`, `{route}`, `{savings_amount}`, `{fee_amount}`.  
**Tradeoff**: A small DB read per template render. Earlier design had templates hardcoded as JS constants; that required a code deploy to change any copy. DB-backed templates are the right call once the operator has preferences.

---

## No public savings wall yet
**Date**: 2026-06  
**Decision**: The public proof strip on the landing page is threshold-gated via env vars (`PROOF_MIN_SAVINGS_CENTS` defaults to $5,000; `PROOF_MIN_TRIPS` defaults to 5). Stats below the thresholds are nulled in the API response and the strip degrades gracefully.  
**Rationale**: An empty or near-empty "savings wall" looks unconvincing and could actively hurt conversion. Better to show nothing than to show one $800 example. The infrastructure is fully built — when real data clears the thresholds, the strip auto-populates.  
**Tradeoff**: No social proof early on. Mitigated by the illustrative examples section (seeded rows labeled clearly as examples) and the fee model explanation.

---

## 10% of documented savings fee model
**Date**: 2026-06  
**Decision**: Revenue is 10% of verified savings (cash benchmark minus award taxes/fees minus other out-of-pocket costs). The fee is computed, presented to the client in a savings report, invoiced, and collected after the trip is booked.  
**Rationale**: Aligns incentives completely: District Award Travel only earns when the client saves. No upfront fee means zero barrier to starting. The savings report with a benchmark screenshot makes the value concrete and defensible.  
**Tradeoff**: Zero revenue if no savings are found (which should be rare — if savings aren't found, there's nothing to book). Revenue is also deferred until booking, which means cash flow lags the work. Accepted — this is the core value proposition.

---

## Boarding-pass visual design for trip cards
**Date**: 2026-06  
**Decision**: Trip cards in the client portal use a boarding-pass aesthetic (left/right panels divided by a perforated line, route in airline caps, cabin class as a secondary label).  
**Rationale**: Echoes the actual product (award flight bookings). Differentiates from generic SaaS list-item dashboards. Reinforces the brand at every touchpoint clients see.  
**Tradeoff**: More CSS complexity than a plain card. A future responsive redesign needs to account for the boarding-pass layout on small screens. Worth it for the brand coherence.

---

## 2026-06-09 — Phase 0 (security hardening)

- **Deleted `/api/setup/*` endpoints** instead of authenticating them. Startup `seed_admin()` already creates/re-syncs the admin from env vars on every boot, so the endpoints were pure attack surface with zero remaining purpose. If login ever breaks, fix the env vars in Render and redeploy — there is deliberately no in-app backdoor anymore.
- **Deleted `/api/intake-create-client` entirely** rather than securing it. The product flow is intake → admin reviews → Accept creates the account. An endpoint that mints accounts + passwords without auth contradicts that flow.
- **Production = `DATABASE_URL` is set.** Simple, zero-config heuristic for Render vs local. Local dev gets an ephemeral `SECRET_KEY` (sessions don't survive restarts — acceptable).
- **Removed EmailJS** rather than proxying it. The backend already sends intake emails over Gmail SMTP; the EmailJS call was a redundant duplicate with a publicly-exposed key. One mail path = fewer failure modes.
- **Intake validation is a hand-rolled dict validator, not a Pydantic model.** The form posts dynamic keys (`trip3_dest`, `pts_united`, …); a rigid model would silently drop them. Cap-everything approach preserves flexibility.

---

## 2026-06-10 — Phase 2 (fulfillment engine)

- **Trips promoted to `trip_requests` table; `clients.data.trips` JSON array untouched.** The JSON blob can't power a kanban board, SLA timers, or append-only event history — all require stable IDs. Keeping the client-portal JSON means zero client-facing change and no refactor of the existing client endpoints. New trips written to both paths going forward; legacy trips importable via `/api/admin/trips/import-legacy`.
- **Backward transitions allowed one step** (e.g. `awaiting_decision → researching` when a client requests new options). Fully blocking backward moves would force a void+recreate dance for a common real-world event. The `workflow_events` audit trail captures every transition regardless.
- **Daily digest via external cron, not in-process scheduler.** Render free tier spins down idle services; an in-process scheduler silently misses the window after any spin-down. Solution: `POST /api/cron/digest?key=CRON_SECRET` endpoint (HMAC-protected) pointed at cron-job.org or a GitHub Actions schedule. Zero new dependencies.
- **Manual time tracking** (start/stop + "+15 min" quick-add) instead of auto-tracking. Auto-tracking browser focus time is unreliable across tabs/devices and has privacy implications. Explicit operator input is more accurate for the effective-hourly-rate metric, which is the only place the data is used.
- **AI circuit breaker state in-process** (not DB). A dyno restart is a reasonable reset of "is the provider down?" — the breaker protects against cascading failures within a session. Simpler, zero overhead, no stale state.
- **Research-checklist check-state in localStorage** (`dat_checklist_{tripId}`), not the DB. Single-operator tool; checked boxes are a personal working aid, not audit data. Avoids a new table + API round-trips for a cosmetic feature.
- **Plan-builder drafts autosave to localStorage** (`dat_plan_draft_{clientEmail}`, debounced 1s), cleared on successful send. Protects against accidental tab closes without server-side draft plumbing; one draft per client is enough for one operator.

---

## 2026-06-10 — Phase 3 (trust surface & conversion)

- **Public proof stats threshold-gated via env vars.** Stats below thresholds are nulled in the JSON response; the proof strip degrades gracefully. The page never looks empty or unconvincing early on.
- **Illustrative examples computed server-side with the real fee function.** 4 seeded rows are computed exactly once at boot using `calc_fee`, so all numbers are internally consistent. Real ledger rows are labeled `"real": true` and returned first.
- **First-party funnel beacon — no cookies, no consent banner.** Random session ID in sessionStorage; tracks page_view / form_start / step_complete / submit events + UTM params. No third-party trackers. No cookies = GDPR-compliant without a consent banner.
- **`consent_at` timestamp stored only when the checkbox is present.** Old cached form pages won't send the consent field — the backend won't 422 them, but new form submissions record the timestamp. Complies with "only if checkbox checked."
- **Proof endpoint returns zero client names or emails ever.** `/api/public/examples` strips names from real ledger rows. `/api/public/proof` returns aggregate numbers only.

---

## 2026-06-10 — Phase 4 (infrastructure hardening)

- **Backups before observability.** The free Render Postgres has no automated backups and an expiry date. One `DROP TABLE` or expired instance loses the entire revenue ledger and client book permanently. Nightly encrypted GitHub Actions backup addresses this first.
- **No keep-alive ping to prevent Render free-tier spin-down.** Keep-alive pings burn the 750 free-hours/mo ceiling. The 5-minute UptimeRobot health check serves as incidental keep-alive. Cold starts (~50s) are acceptable for a portal with a handful of clients.
- **Email via daemon thread + BackgroundTasks, not an async task queue.** No Redis, no Celery, no external service. Sufficient for single-operator volume. Three-attempt retry with 5s/25s backoff logged to `email_log` table. The `_email_transport` seam makes provider swapping config-only.
- **Connection pool pinned explicitly** (pool_size=5, max_overflow=5, pool_recycle=300, pool_timeout=10). Recycle=300 is cheaper than pool_pre_ping alone for long-idle Render connections. Hard cap of 10 connections from this process vs Render Postgres's ~95 usable limit.
- **`ENV` defaults to production when `DATABASE_URL` is set.** Safe-by-default: a service that forgets the `ENV` var gets production behavior (strict secrets, seed scripts refuse to run). Staging must opt in via `ENV=staging`. Tested in `test_seed_guard.py`.
