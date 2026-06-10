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

- **Research-checklist check-state lives in localStorage** (`dat_checklist_{tripId}`),
  not the DB. Single-operator tool; the checked boxes are a personal working aid, not
  audit data. Avoids a new table + API round-trips for a cosmetic feature.

- **Structured option fields are composed into the `desc` string client-side** before
  sending. The existing message/plan pipeline (`POST /api/admin/send-message` with
  `plan_details.options[{num,desc,img}]`) and the client portal renderer stay completely
  unchanged — zero backend or portal migration for richer option cards.

- **Plan-builder drafts autosave to localStorage** (`dat_plan_draft_{clientEmail}`,
  debounced 1s) and clear on successful send. Protects against accidental tab closes
  without server-side draft plumbing; one draft per client is enough for one operator.

---

## 2026-06-10 — Phase 3 (trust surface & conversion)

- **Public proof stats threshold-gated** via env vars (defaults: $5k savings / 5 trips / 3 records for ¢/pt). Stats below thresholds are nulled in the JSON response; the hero proof strip degrades gracefully (1–2 stats, or hidden entirely). The page never looks small or unconvincing early on. As the business grows, more data auto-surfaces.

- **Illustrative examples computed server-side with the real fee function.** 4 seeded rows (Tokyo business, Paris premium, Cancun family, Maui hotel) are computed exactly once at boot using `calc_fee`, so all numbers are internally consistent. Real ledger rows (booked+invoiced+paid records, no names/emails) are labeled `"real": true` and returned first. Server logic prevents a fake row ever rendering as real — label is part of the response schema, tested.

- **First-party funnel beacon — no cookies, no consent banner.** Random session ID in sessionStorage (cleared on tab close); tracks page_view / form_start / step_complete / submit events. UTM params captured from URL. Stored in `funnel_events` table. No third-party trackers. No cookies means GDPR-compliant without a consent banner (which kills conversion).

- **`consent_at` timestamp stored only when the checkbox is present.** Old cached form pages won't send the consent field — the backend won't 422 them (safe), but new form submissions include `consent: "true"` and the timestamp is recorded. Complies with "only if checkbox checked" requirement.

- **Legal pages behind `LEGAL_DRAFT = true;` flag.** Both pages (terms.html, privacy.html) carry an amber "DRAFT — pending review" banner. User flips the flag in the page source after parent/legal review. No need for a config file or env var — just a boolean at the top of the script section.

- **Proof endpoint returns zero client names or emails ever.** GET `/api/public/examples` strips names from real ledger rows (only route = trip_label, no client emails). GET `/api/public/proof` returns aggregate numbers only. Tested: assert no names/emails appear in the JSON response.

- **Research-checklist check-state lives in localStorage** (`dat_checklist_{tripId}`),
  not the DB. Single-operator tool; the checked boxes are a personal working aid, not
  audit data. Avoids a new table + API round-trips for a cosmetic feature.

- **Structured option fields are composed into the `desc` string client-side** before
  sending. The existing message/plan pipeline (`POST /api/admin/send-message` with
  `plan_details.options[{num,desc,img}]`) and the client portal renderer stay completely
  unchanged — zero backend or portal migration for richer option cards.

- **Plan-builder drafts autosave to localStorage** (`dat_plan_draft_{clientEmail}`,
  debounced 1s) and clear on successful send. Protects against accidental tab closes
  without server-side draft plumbing; one draft per client is enough for one operator.
