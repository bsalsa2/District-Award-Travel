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
