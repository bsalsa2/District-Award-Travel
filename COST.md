# COST.md — what this costs and what's worth paying for

Current monthly cost: **$0**. Everything runs on free tiers.

---

## What's free today

| Service | Free tier limits | Where we hit the wall |
|---|---|---|
| Render web service | 750 free hours/mo, spins down after 15 min idle (~50s cold start) | First request after idle; SSE reconnects on wake |
| Render Postgres | 1 DB, 256MB storage, **expires 30 days (free tier) or 90 days (Postgres free tier) — check dashboard** | Data loss when it expires; no automated backups |
| GitHub Actions | 2,000 min/mo (public repo: unlimited) | Nightly backup is <1 min; not a concern |
| Gmail SMTP | ~500 recipients/day, increasingly spam-foldered for strangers | ~50+ intakes/day; deliverability issues now |
| Groq API | Free tier, rate-limited | Heavy usage; circuit breaker handles outages |
| Gemini API | Free tier, rate-limited | Heavy usage; circuit breaker handles outages |
| UptimeRobot | 50 monitors, 5-min interval | Fine indefinitely |

---

## Ranked paid upgrades

### #1 — Render Starter Postgres (~$7/mo) ← DO THIS FIRST

**Why:** The free Postgres expires. When it does, all client PII, the savings ledger, and the trip history are gone permanently. This is the single biggest risk in the system (flagged as Risk #1 in INFRA_AUDIT.md since Phase 0).

**What you get:** No expiry, daily automated backups with point-in-time recovery, 10GB storage. The nightly encrypted GitHub Actions backup stays as a second layer.

**When:** Before the free Postgres expiry date shown in your Render dashboard.

---

### #2 — Resend or Brevo for transactional email (~$0–20/mo)

**Why:** Gmail SMTP has a ~500/day cap and increasingly spam-folders mail sent from @gmail.com to strangers. A transactional provider (Resend, Brevo, Postmark) gives:
- 10× the daily volume on free tiers
- SPF/DKIM/DMARC alignment (your domain in From:, not gmail.com)
- Delivery dashboard + bounce/spam tracking
- One `_email_transport` swap in `backend/main.py` to migrate

**Resend:** 3,000/mo free, $20/mo for 50k. Best DX. Recommended if you're adding a custom domain anyway.
**Brevo:** 300/day free, $25/mo for 20k. Good fallback.

**When:** When intake volume grows or you start getting "not in spam" complaints.

---

### #3 — Render Starter web service (~$7/mo)

**Why:** Eliminates the 50s cold start and the 750 free-hours cap. The free tier is acceptable while you have a handful of clients; once clients are checking the portal daily, a 50s wait on first load is unprofessional.

**What you get:** Always-on, no spin-down, no free-hours clock.

**When:** When you have 10+ active clients checking the portal regularly.

---

### #4 — Sentry error monitoring (free tier is fine)

**Why:** The app already supports `SENTRY_DSN` — set the env var and every 500 error lands in Sentry with a full traceback, user context, and stack trace. The email-on-500 in the current code is a fallback; Sentry is faster and searchable.

**Cost:** Free for 5k errors/mo, which covers years of this business.

**When:** Now, actually — it's free and setup takes 5 minutes.

---

### #5 — Custom domain + SSL (~$10–15/yr)

**Why:** `districtawardtravel.com` in the From: address builds trust. Required for SPF/DKIM alignment (upgrade #2 depends on this). Render serves SSL for free once the domain is pointed.

**When:** Before you start pitching referrals or running ads.

---

## What's NOT worth paying for now

- **Render Team / Org plans** — single operator, no need
- **Dedicated DB instances** — overkill at current data size
- **Full Sentry paid plan** — free tier covers this business for years
- **Groq/Gemini paid tiers** — circuit breaker + manual fallbacks handle outages gracefully; upgrade when AI becomes load-critical
