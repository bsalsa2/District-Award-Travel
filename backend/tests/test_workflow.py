import datetime as dt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    WORKFLOW_TRANSITIONS, REASON_REQUIRED_STATUSES,
    is_valid_workflow_transition,
    trip_attention_flags,
    render_template,
    Client, TripRequest, WorkflowEvent,
    hash_pw, make_token,
)

# ── In-memory SQLite test DB ────────────────────────────────────────────────
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ADMIN_TOKEN = make_token("admin@test.com", "admin")
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def _make_client(db, email="test@example.com", name="Test User"):
    c = Client(email=email, password_hash=hash_pw("pw"), name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── Transition matrix ───────────────────────────────────────────────────────
@pytest.mark.parametrize("frm,to,expected", [
    ("new", "researching", True),
    ("new", "declined", True),
    ("new", "lost", True),
    ("researching", "options_sent", True),
    ("researching", "new", True),
    ("options_sent", "awaiting_decision", True),
    ("awaiting_decision", "booked", True),
    ("booked", "closed", True),
    # illegal
    ("new", "booked", False),
    ("new", "closed", False),
    ("closed", "new", False),
    ("closed", "researching", False),
    ("declined", "new", False),
    ("declined", "researching", False),
    ("booked", "researching", False),
    ("booked", "awaiting_decision", False),
])
def test_transition_matrix(frm, to, expected):
    assert is_valid_workflow_transition(frm, to) is expected


def test_reason_required_statuses():
    assert "declined" in REASON_REQUIRED_STATUSES
    assert "lost" in REASON_REQUIRED_STATUSES
    assert "closed" not in REASON_REQUIRED_STATUSES


# ── Aging / attention flags ─────────────────────────────────────────────────
def frozen(hours_ago):
    return dt.datetime.utcnow() - dt.timedelta(hours=hours_ago)


def test_new_at_23h_ok():
    f = trip_attention_flags("new", frozen(23), frozen(23), now=dt.datetime.utcnow())
    assert f["level"] == "ok"
    assert not f["follow_up"]


def test_new_at_25h_amber():
    f = trip_attention_flags("new", frozen(25), frozen(25), now=dt.datetime.utcnow())
    assert f["level"] == "amber"


def test_new_at_49h_red():
    f = trip_attention_flags("new", frozen(49), frozen(49), now=dt.datetime.utcnow())
    assert f["level"] == "red"


def test_options_sent_idle_73h_followup():
    now = dt.datetime.utcnow()
    stage_entered = now - dt.timedelta(hours=100)
    last_activity = now - dt.timedelta(hours=73)
    f = trip_attention_flags("options_sent", stage_entered, last_activity, now=now)
    assert f["follow_up"] is True
    assert f["level"] == "amber"


def test_options_sent_idle_10h_ok():
    now = dt.datetime.utcnow()
    f = trip_attention_flags("options_sent", frozen(10), frozen(10), now=now)
    assert f["level"] == "ok"
    assert not f["follow_up"]


# ── render_template ─────────────────────────────────────────────────────────
def test_render_full_substitution():
    result = render_template("Hi {first_name}, your route is {route}.", {"first_name": "Alex", "route": "JFK → LHR"})
    assert result == "Hi Alex, your route is JFK → LHR."


def test_render_missing_variable_left_literal():
    result = render_template("Hi {first_name}, your fee is {fee_amount}.", {"first_name": "Alex"})
    assert "{fee_amount}" in result
    assert "Alex" in result


def test_render_empty_variables():
    body = "Hello {first_name}!"
    assert render_template(body, {}) == body


# ── API endpoint tests ──────────────────────────────────────────────────────
def test_board_requires_auth():
    resp = client.get("/api/admin/board")
    assert resp.status_code == 401


def test_trip_status_illegal_jump():
    db = TestingSession()
    c = _make_client(db, "jump@test.com")
    trip = TripRequest(client_id=c.id, destination="Tokyo", workflow_status="new")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    resp = client.patch(f"/api/admin/trips/{trip.id}/status", json={"new_status": "booked", "note": ""}, headers=AUTH)
    assert resp.status_code == 400
    db.close()


def test_trip_status_declined_requires_reason():
    db = TestingSession()
    c = _make_client(db, "declined@test.com")
    trip = TripRequest(client_id=c.id, destination="Paris", workflow_status="new")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    resp = client.patch(f"/api/admin/trips/{trip.id}/status", json={"new_status": "declined", "note": ""}, headers=AUTH)
    assert resp.status_code == 422
    db.close()


def test_trip_status_declined_with_reason_ok():
    db = TestingSession()
    c = _make_client(db, "declined2@test.com")
    trip = TripRequest(client_id=c.id, destination="Paris", workflow_status="new")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    resp = client.patch(f"/api/admin/trips/{trip.id}/status", json={"new_status": "declined", "note": "Client went direct"}, headers=AUTH)
    assert resp.status_code == 200
    db.close()


def test_trip_events_returned():
    db = TestingSession()
    c = _make_client(db, "events@test.com")
    trip = TripRequest(client_id=c.id, destination="Rome", workflow_status="new")
    db.add(trip)
    db.flush()
    db.add(WorkflowEvent(trip_id=trip.id, from_status="", to_status="new"))
    db.commit()
    db.refresh(trip)
    resp = client.get(f"/api/admin/trips/{trip.id}/events", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    db.close()


def test_booked_prompt_savings_record():
    db = TestingSession()
    c = _make_client(db, "booked@test.com")
    trip = TripRequest(client_id=c.id, destination="Bali", workflow_status="awaiting_decision")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    resp = client.patch(f"/api/admin/trips/{trip.id}/status", json={"new_status": "booked", "note": ""}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json().get("prompt_savings_record") is True
    db.close()
