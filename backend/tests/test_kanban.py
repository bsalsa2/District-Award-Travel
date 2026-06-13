"""Tests for the kanban board API and trip-advance shortcut endpoint."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    NEXT_STATUS,
    Client, TripRequest, WorkflowEvent,
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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ADMIN_TOKEN = make_token("admin@kanban.test", "admin")
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def _client(db, email="c@kanban.test"):
    c = Client(email=email, password_hash=hash_pw("pw"), name="Kanban Client")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _trip(db, client_id, status="new", dest="Tokyo"):
    t = TripRequest(client_id=client_id, destination=dest, workflow_status=status)
    db.add(t); db.commit(); db.refresh(t)
    return t


# ── Board endpoint ───────────────────────────────────────────────────────────

def test_board_requires_admin():
    r = client.get("/api/admin/board")
    assert r.status_code in (401, 403)


def test_board_returns_columns():
    r = client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert "columns" in body
    assert "needs_attention" in body
    # should have at least the active columns
    for col in ("new", "researching", "options_sent"):
        assert col in body["columns"]


def test_board_includes_trip():
    with TestingSession() as db:
        c = _client(db, "board@kanban.test")
        _trip(db, c.id, status="new", dest="Paris")
    r = client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    trips_new = r.json()["columns"].get("new", [])
    assert any(t["destination"] == "Paris" for t in trips_new)


# ── /advance shortcut ────────────────────────────────────────────────────────

def test_advance_requires_admin():
    with TestingSession() as db:
        c = _client(db, "adv_anon@kanban.test")
        t = _trip(db, c.id)
    r = client.post(f"/api/admin/trips/{t.id}/advance")
    assert r.status_code in (401, 403)


def test_advance_new_to_researching():
    with TestingSession() as db:
        c = _client(db, "adv1@kanban.test")
        t = _trip(db, c.id, status="new")
    r = client.post(f"/api/admin/trips/{t.id}/advance", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["workflow_status"] == "researching"


def test_advance_creates_workflow_event():
    with TestingSession() as db:
        c = _client(db, "adv2@kanban.test")
        t = _trip(db, c.id, status="new")
    client.post(f"/api/admin/trips/{t.id}/advance", headers=AUTH)
    with TestingSession() as db:
        events = db.query(WorkflowEvent).filter(WorkflowEvent.trip_id == t.id).all()
    assert len(events) == 1
    assert events[0].from_status == "new"
    assert events[0].to_status == "researching"


@pytest.mark.parametrize("start,expected_next", NEXT_STATUS.items())
def test_advance_each_active_status(start, expected_next):
    with TestingSession() as db:
        c = _client(db, f"adv_{start}@kanban.test")
        t = _trip(db, c.id, status=start)
    r = client.post(f"/api/admin/trips/{t.id}/advance", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["workflow_status"] == expected_next


def test_advance_from_closed_returns_400():
    with TestingSession() as db:
        c = _client(db, "advclosed@kanban.test")
        t = _trip(db, c.id, status="closed")
    r = client.post(f"/api/admin/trips/{t.id}/advance", headers=AUTH)
    assert r.status_code == 400


def test_advance_booked_sets_prompt_savings():
    with TestingSession() as db:
        c = _client(db, "adv_book@kanban.test")
        t = _trip(db, c.id, status="awaiting_decision")
    r = client.post(f"/api/admin/trips/{t.id}/advance", headers=AUTH)
    assert r.status_code == 200
    assert r.json().get("prompt_savings_record") is True


def test_advance_missing_trip_returns_404():
    r = client.post("/api/admin/trips/999999/advance", headers=AUTH)
    assert r.status_code == 404


# ── NEXT_STATUS completeness ─────────────────────────────────────────────────

def test_next_status_maps_only_active_states():
    terminal = {"closed", "declined", "lost"}
    for start, nxt in NEXT_STATUS.items():
        assert start not in terminal, f"NEXT_STATUS should not map terminal state {start}"
        assert nxt != start, f"NEXT_STATUS should advance, not stay: {start}"


def test_board_stale_flag_present():
    """Board rows expose the 'stale' and 'level' keys needed by the kanban UI."""
    with TestingSession() as db:
        c = _client(db, "stale@kanban.test")
        _trip(db, c.id, status="researching", dest="StaleCity")
    r = client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    for col_trips in r.json()["columns"].values():
        for row in col_trips:
            assert "stale" in row
            assert "level" in row
            assert "hours_in_stage" in row
