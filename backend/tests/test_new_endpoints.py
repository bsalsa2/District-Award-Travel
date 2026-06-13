"""Tests for endpoints without prior coverage:
- GET /api/public/stats  (no auth)
- GET /api/admin/export/clients  (admin)
- GET /api/admin/export/savings  (admin)
- PATCH /api/client/preferences  (client auth)
"""
import csv
import io
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


http = TestClient(app)

ADMIN_TOKEN = make_token("admin@newep.test", "admin")
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

CLIENT_EMAIL = "client@newep.test"
CLIENT_TOKEN = make_token(CLIENT_EMAIL, "client")
CLIENT_AUTH = {"Authorization": f"Bearer {CLIENT_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_db():
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


def _add_client(db, email=CLIENT_EMAIL, name="Test Client"):
    c = Client(email=email, password_hash=hash_pw("pw"), name=name)
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


def _add_savings(db, client_id, cash=300000, taxes=10000, other=0, status="booked"):
    r = SavingsRecord(
        client_id=client_id,
        trip_label="IAD → Rome · Business",
        cash_benchmark_cents=cash,
        award_taxes_fees_cents=taxes,
        other_out_of_pocket_cents=other,
        fee_rate_bps=1000,
        status=status,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ── GET /api/public/stats ─────────────────────────────────────────────────────

def test_public_stats_no_auth_required():
    r = http.get("/api/public/stats")
    assert r.status_code == 200


def test_public_stats_shape():
    r = http.get("/api/public/stats")
    body = r.json()
    assert "total_savings_cents" in body
    assert "trips_completed" in body
    assert "avg_savings_cents" in body


def test_public_stats_empty_db():
    r = http.get("/api/public/stats")
    body = r.json()
    assert body["total_savings_cents"] == 0
    assert body["trips_completed"] == 0
    assert body["avg_savings_cents"] == 0


def test_public_stats_counts_only_qualifying_records():
    db = TestingSession()
    c = _add_client(db)
    # booked/invoiced/paid should count
    _add_savings(db, c.id, cash=200000, taxes=10000, status="booked")
    _add_savings(db, c.id, cash=400000, taxes=20000, status="paid")
    # draft should NOT count
    _add_savings(db, c.id, cash=999999, taxes=0, status="draft")
    db.close()

    r = http.get("/api/public/stats")
    body = r.json()
    # gross: (200000-10000) + (400000-20000) = 190000 + 380000 = 570000
    assert body["total_savings_cents"] == 570000
    assert body["trips_completed"] == 2
    assert body["avg_savings_cents"] == 285000


# ── GET /api/admin/export/clients ─────────────────────────────────────────────

def test_export_clients_requires_auth():
    r = http.get("/api/admin/export/clients")
    assert r.status_code in (401, 403)


def test_export_clients_rejects_client_role():
    r = http.get("/api/admin/export/clients", headers=CLIENT_AUTH)
    assert r.status_code in (401, 403)


def test_export_clients_returns_csv():
    r = http.get("/api/admin/export/clients", headers=ADMIN_AUTH)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


def test_export_clients_csv_has_header():
    r = http.get("/api/admin/export/clients", headers=ADMIN_AUTH)
    reader = csv.reader(io.StringIO(r.text))
    header = next(reader)
    assert "id" in header
    assert "email" in header
    assert "name" in header


def test_export_clients_data_row():
    db = TestingSession()
    c = _add_client(db, email="export_c@newep.test", name="Export Person")
    db.close()

    r = http.get("/api/admin/export/clients", headers=ADMIN_AUTH)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text)))
    # rows[0] is header; find data row
    emails = [row[2] for row in rows[1:]]
    assert "export_c@newep.test" in emails


# ── GET /api/admin/export/savings ─────────────────────────────────────────────

def test_export_savings_requires_auth():
    r = http.get("/api/admin/export/savings")
    assert r.status_code in (401, 403)


def test_export_savings_rejects_client_role():
    r = http.get("/api/admin/export/savings", headers=CLIENT_AUTH)
    assert r.status_code in (401, 403)


def test_export_savings_returns_csv():
    r = http.get("/api/admin/export/savings", headers=ADMIN_AUTH)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


def test_export_savings_csv_has_header():
    r = http.get("/api/admin/export/savings", headers=ADMIN_AUTH)
    reader = csv.reader(io.StringIO(r.text))
    header = next(reader)
    assert "id" in header
    assert "client_email" in header
    assert "trip_label" in header
    assert "status" in header


def test_export_savings_data_row():
    db = TestingSession()
    c = _add_client(db, email="saver@newep.test", name="Saver Person")
    _add_savings(db, c.id, cash=500000, taxes=25000, status="paid")
    db.close()

    r = http.get("/api/admin/export/savings", headers=ADMIN_AUTH)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text)))
    emails = [row[2] for row in rows[1:]]  # client_email is col index 2
    assert "saver@newep.test" in emails
    # gross_savings_dollars = (500000 - 25000) / 100 = 4750.0
    gross_col = [row[4] for row in rows[1:] if row[2] == "saver@newep.test"]
    assert gross_col and float(gross_col[0]) == pytest.approx(4750.0)


# ── PATCH /api/client/preferences ────────────────────────────────────────────

def test_client_preferences_requires_auth():
    r = http.patch("/api/client/preferences", json={"dark_mode": True})
    assert r.status_code in (401, 403)


def test_client_preferences_rejects_admin_role():
    r = http.patch("/api/client/preferences", json={"dark_mode": True}, headers=ADMIN_AUTH)
    assert r.status_code in (401, 403)


def test_client_preferences_happy_path():
    db = TestingSession()
    _add_client(db, email=CLIENT_EMAIL)
    db.close()

    r = http.patch("/api/client/preferences", json={"dark_mode": True, "email_notifications": False}, headers=CLIENT_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["preferences"]["dark_mode"] is True
    assert body["preferences"]["email_notifications"] is False


def test_client_preferences_persisted_in_db():
    db = TestingSession()
    c = _add_client(db, email=CLIENT_EMAIL)
    db.close()

    http.patch("/api/client/preferences", json={"dark_mode": True}, headers=CLIENT_AUTH)

    db = TestingSession()
    refreshed = db.query(Client).filter(Client.email == CLIENT_EMAIL).first()
    import json
    prefs = json.loads(refreshed.data or "{}").get("preferences", {})
    db.close()
    assert prefs.get("dark_mode") is True


def test_client_preferences_partial_update_preserves_existing():
    db = TestingSession()
    import json
    c = _add_client(db, email=CLIENT_EMAIL)
    c.data = json.dumps({"preferences": {"dark_mode": True, "email_notifications": True}})
    db.commit()
    db.close()

    r = http.patch("/api/client/preferences", json={"email_notifications": False}, headers=CLIENT_AUTH)
    assert r.status_code == 200
    prefs = r.json()["preferences"]
    # dark_mode should remain True
    assert prefs["dark_mode"] is True
    assert prefs["email_notifications"] is False
