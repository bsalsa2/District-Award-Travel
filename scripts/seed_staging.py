#!/usr/bin/env python3
"""Seed OBVIOUSLY-FAKE data for development/staging.

Every client is named "TEST ...", every email is @example.com (a reserved
domain that can never receive mail). HARD-REFUSES to run in production:
both the ENV check and the data shape make prod contamination impossible.

Usage:
    ENV=staging python3 scripts/seed_staging.py
    python3 scripts/seed_staging.py          # local dev (no DATABASE_URL) is fine
"""
import os
import sys
import datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.main import (  # noqa: E402
    ENV, SessionLocal, hash_pw,
    Client, Intake, TripRequest, SavingsRecord, WorkflowEvent,
)

# ── THE GUARD ───────────────────────────────────────────────────────────────
if ENV not in ("development", "staging"):
    print(f"REFUSING TO RUN: ENV={ENV!r}. Seed data never touches production.")
    print("If this IS a staging box, set ENV=staging explicitly and re-run.")
    sys.exit(1)

FAKE_CLIENTS = [
    ("TEST Alice Example",  "test-alice@example.com"),
    ("TEST Bob Example",    "test-bob@example.com"),
    ("TEST Carol Example",  "test-carol@example.com"),
]

db = SessionLocal()
try:
    if db.query(Client).filter(Client.email.like("%@example.com")).count():
        print("Fake data already present — nothing to do (idempotent).")
        sys.exit(0)

    now = dt.datetime.utcnow()
    for i, (name, email) in enumerate(FAKE_CLIENTS):
        c = Client(
            email=email, password_hash=hash_pw("test-password"), name=name,
            data='{"points":[{"program":"TEST Chase Ultimate Rewards","balance":"100,000"}],"trips":[]}',
        )
        db.add(c)
        db.flush()
        trip = TripRequest(
            client_id=c.id, destination=f"TEST-DEST-{i}", origin="IAD",
            dates="TEST dates", workflow_status="new",
            stage_entered_at=now - dt.timedelta(hours=30 * i),   # one card aged amber
            last_activity_at=now - dt.timedelta(hours=30 * i),
        )
        db.add(trip)
        db.flush()
        db.add(WorkflowEvent(trip_id=trip.id, from_status="", to_status="new", note="seeded"))
        db.add(SavingsRecord(
            client_id=c.id, trip_label=f"TEST trip {i}",
            cash_benchmark_cents=250000 + i * 10000, award_taxes_fees_cents=11200,
            points_used=75000, points_program="TEST program",
            status=["draft", "booked", "paid"][i % 3],
            benchmark_captured_at=now,
        ))
    db.add(Intake(
        first_name="TEST", last_name="Intake", email="test-intake@example.com",
        payload='{"first_name":"TEST","last_name":"Intake","email":"test-intake@example.com"}',
    ))
    db.commit()
    print(f"Seeded {len(FAKE_CLIENTS)} TEST clients (+trips, savings) and 1 TEST intake. ENV={ENV}")
finally:
    db.close()
