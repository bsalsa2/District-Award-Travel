import datetime as dt
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    Base, build_digest,
    Client, TripRequest, WorkflowEvent, Intake, SavingsRecord,
    hash_pw,
)

TEST_DB_URL = "sqlite://"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()


def test_digest_counts_new_intakes(db):
    now = dt.datetime.utcnow()
    db.add(Intake(first_name="A", last_name="B", email="a@b.com", created_at=now - dt.timedelta(hours=2)))
    db.add(Intake(first_name="C", last_name="D", email="c@d.com", created_at=now - dt.timedelta(hours=30)))
    db.commit()
    digest = build_digest(db, now=now)
    assert digest["new_intakes_24h"] == 1
    assert digest["total_pending_intakes"] == 2


def test_digest_stale_trips(db):
    now = dt.datetime.utcnow()
    c = Client(email="stale@test.com", password_hash=hash_pw("pw"), name="Stale User")
    db.add(c)
    db.flush()
    trip = TripRequest(
        client_id=c.id,
        destination="Tokyo",
        workflow_status="new",
        stage_entered_at=now - dt.timedelta(hours=50),
        last_activity_at=now - dt.timedelta(hours=50),
    )
    db.add(trip)
    db.commit()
    digest = build_digest(db, now=now)
    assert len(digest["stale_trips"]) == 1
    assert digest["stale_trips"][0]["level"] == "red"
    assert digest["stale_trips"][0]["destination"] == "Tokyo"


def test_digest_outstanding_invoices(db):
    now = dt.datetime.utcnow()
    c = Client(email="inv@test.com", password_hash=hash_pw("pw"), name="Invoice User")
    db.add(c)
    db.flush()
    sr = SavingsRecord(
        client_id=c.id,
        trip_label="Paris Trip",
        cash_benchmark_cents=400000,
        status="invoiced",
        invoice_number="DAT-2026-0001",
        fee_rate_bps=1000,
    )
    db.add(sr)
    db.commit()
    digest = build_digest(db, now=now)
    assert len(digest["outstanding_invoices"]) == 1
    assert digest["outstanding_invoices"][0]["invoice_number"] == "DAT-2026-0001"
    assert digest["outstanding_invoices"][0]["fee_cents"] == 40000


def test_digest_awaiting_decision(db):
    now = dt.datetime.utcnow()
    c = Client(email="await@test.com", password_hash=hash_pw("pw"), name="Awaiting User")
    db.add(c)
    db.flush()
    trip = TripRequest(
        client_id=c.id,
        destination="London",
        workflow_status="awaiting_decision",
        stage_entered_at=now - dt.timedelta(hours=5),
        last_activity_at=now - dt.timedelta(hours=5),
    )
    db.add(trip)
    db.commit()
    digest = build_digest(db, now=now)
    assert any(t["destination"] == "London" for t in digest["awaiting_decision_trips"])
