"""Tests for GET /api/admin/stats endpoint."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    Client, TripRequest, SavingsRecord,
    hash_pw, make_token,
)

TEST_DB_URL = "sqlite://"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)

ADMIN_TOKEN = make_token("admin@stats.test", "admin")
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

EXPECTED_KEYS = {
    "trips_by_status",
    "total_clients",
    "total_trips",
    "active_trips",
    "total_savings_cents",
    "total_fees_cents",
    "avg_savings_per_trip_cents",
    "trips_stale",
    "new_clients_this_week",
}


@pytest.fixture(autouse=True)
def _set_db():
    # Wipe tables before each test
    db = TestingSession()
    try:
        db.query(SavingsRecord).delete()
        db.query(TripRequest).delete()
        db.query(Client).delete()
        db.commit()
    finally:
        db.close()
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev


def _add_client(db, email="c@stats.test"):
    c = Client(email=email, password_hash=hash_pw("pw"), name="Stats Client")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _add_trip(db, client_id, status="new"):
    t = TripRequest(client_id=client_id, destination="Paris", workflow_status=status)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_stats_requires_auth():
    r = client.get("/api/admin/stats")
    assert r.status_code in (401, 403)


def test_stats_rejects_non_admin():
    user_token = make_token("user@stats.test", "client")
    r = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code in (401, 403)


# ── Shape test ────────────────────────────────────────────────────────────────

def test_stats_returns_expected_keys():
    r = client.get("/api/admin/stats", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert EXPECTED_KEYS.issubset(data.keys())


def test_stats_empty_db():
    r = client.get("/api/admin/stats", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["total_clients"] == 0
    assert data["total_trips"] == 0
    assert data["active_trips"] == 0
    assert data["trips_stale"] == 0
    assert data["total_savings_cents"] == 0


# ── Count increment tests ─────────────────────────────────────────────────────

def test_stats_counts_clients_and_trips():
    db = TestingSession()
    try:
        c1 = _add_client(db, "a@stats.test")
        c2 = _add_client(db, "b@stats.test")
        _add_trip(db, c1.id, "new")
        _add_trip(db, c1.id, "researching")
        _add_trip(db, c2.id, "booked")
    finally:
        db.close()

    r = client.get("/api/admin/stats", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["total_clients"] == 2
    assert data["total_trips"] == 3
    # booked is terminal; new and researching are active
    assert data["active_trips"] == 2
    assert data["trips_by_status"].get("new", 0) == 1
    assert data["trips_by_status"].get("researching", 0) == 1
    assert data["trips_by_status"].get("booked", 0) == 1


def test_stats_savings_totals():
    db = TestingSession()
    try:
        c = _add_client(db, "saver@stats.test")
        rec = SavingsRecord(
            client_id=c.id,
            trip_label="Hawaii",
            cash_benchmark_cents=500000,
            award_taxes_fees_cents=20000,
            other_out_of_pocket_cents=0,
            fee_rate_bps=1000,
            status="booked",
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()

    r = client.get("/api/admin/stats", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    # gross = 500000 - 20000 = 480000
    assert data["total_savings_cents"] == 480000
    # fee = 10% of 480000 = 48000
    assert data["total_fees_cents"] == 48000
    assert data["avg_savings_per_trip_cents"] == 480000


def test_stats_new_clients_this_week():
    db = TestingSession()
    try:
        _add_client(db, "new1@stats.test")
        _add_client(db, "new2@stats.test")
    finally:
        db.close()

    r = client.get("/api/admin/stats", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["new_clients_this_week"] == 2
