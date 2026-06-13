"""Tests for the kanban pipeline: stale flags, workflow transitions, board columns."""
import datetime as dt
import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    _trip_row, trip_attention_flags,
    WORKFLOW_TRANSITIONS, WORKFLOW_STATUSES,
    NEXT_STATUS,
    is_valid_workflow_transition,
    Client, TripRequest,
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


http_client = TestClient(app)

ADMIN_TOKEN = make_token("admin@pipeline.test", "admin")
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_db():
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    # Reset DB state for each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev


def _make_trip(status="new", stage_entered_at=None, last_activity_at=None, destination="TestCity"):
    """Build a plain namespace that duck-types a TripRequest for _trip_row()."""
    now = dt.datetime.utcnow()
    return types.SimpleNamespace(
        id=1,
        client_id=1,
        destination=destination,
        origin=None,
        dates=None,
        passengers=None,
        cabin=None,
        flexibility=None,
        workflow_status=status,
        stage_entered_at=stage_entered_at or now,
        last_activity_at=last_activity_at or now,
        savings_record_id=None,
        time_tracked_minutes=0,
        notes="[]",
        created_at=now,
        research_notes="",
    )


# ── _trip_row stale flag ──────────────────────────────────────────────────────

def test_trip_row_stale_true_red_when_60h_researching():
    """60 hours in 'researching' → stale=True, level='red'."""
    now = dt.datetime.utcnow()
    stage_entered_at = now - dt.timedelta(hours=60)
    trip = _make_trip(status="researching", stage_entered_at=stage_entered_at, last_activity_at=stage_entered_at)
    row = _trip_row(trip, now=now)
    assert row["stale"] is True
    assert row["level"] == "red"


def test_trip_row_not_stale_when_1h_researching():
    """1 hour in 'researching' → stale=False, level='ok'."""
    now = dt.datetime.utcnow()
    stage_entered_at = now - dt.timedelta(hours=1)
    trip = _make_trip(status="researching", stage_entered_at=stage_entered_at, last_activity_at=stage_entered_at)
    row = _trip_row(trip, now=now)
    assert row["stale"] is False
    assert row["level"] == "ok"


# ── _trip_row booked not stale ────────────────────────────────────────────────

def test_trip_row_booked_never_stale():
    """'booked' status is excluded from staleness even if 200h old."""
    now = dt.datetime.utcnow()
    stage_entered_at = now - dt.timedelta(hours=200)
    trip = _make_trip(status="booked", stage_entered_at=stage_entered_at, last_activity_at=stage_entered_at)
    row = _trip_row(trip, now=now)
    assert row["stale"] is False


def test_trip_row_closed_never_stale():
    """'closed' status is excluded from staleness."""
    now = dt.datetime.utcnow()
    stage_entered_at = now - dt.timedelta(hours=200)
    trip = _make_trip(status="closed", stage_entered_at=stage_entered_at, last_activity_at=stage_entered_at)
    row = _trip_row(trip, now=now)
    assert row["stale"] is False


def test_trip_row_declined_never_stale():
    """'declined' status is excluded from staleness."""
    now = dt.datetime.utcnow()
    stage_entered_at = now - dt.timedelta(hours=200)
    trip = _make_trip(status="declined", stage_entered_at=stage_entered_at, last_activity_at=stage_entered_at)
    row = _trip_row(trip, now=now)
    assert row["stale"] is False


# ── WORKFLOW_TRANSITIONS completeness ─────────────────────────────────────────

def test_workflow_transitions_cover_all_next_status_sources():
    """Every status in NEXT_STATUS should also be a valid source in WORKFLOW_TRANSITIONS."""
    for src_status in NEXT_STATUS:
        assert src_status in WORKFLOW_TRANSITIONS, (
            f"NEXT_STATUS has source '{src_status}' but it's missing from WORKFLOW_TRANSITIONS"
        )


def test_workflow_transitions_next_status_targets_are_valid():
    """Every target in NEXT_STATUS should exist as a key in WORKFLOW_TRANSITIONS."""
    for src_status, target_status in NEXT_STATUS.items():
        assert target_status in WORKFLOW_TRANSITIONS, (
            f"NEXT_STATUS maps '{src_status}' -> '{target_status}', "
            f"but '{target_status}' is not a valid workflow status"
        )


def test_workflow_transitions_next_status_are_allowed():
    """Each NEXT_STATUS advance must be an allowed transition in WORKFLOW_TRANSITIONS."""
    for src_status, target_status in NEXT_STATUS.items():
        assert is_valid_workflow_transition(src_status, target_status), (
            f"NEXT_STATUS says {src_status} -> {target_status}, "
            f"but WORKFLOW_TRANSITIONS forbids it"
        )


# ── is_valid_workflow_transition ──────────────────────────────────────────────

@pytest.mark.parametrize("current,new,expected", [
    # Valid forward transitions
    ("new", "researching", True),
    ("new", "declined", True),
    ("new", "lost", True),
    ("researching", "options_sent", True),
    ("options_sent", "awaiting_decision", True),
    ("awaiting_decision", "booked", True),
    ("booked", "closed", True),
    # Valid backward / lateral transitions
    ("researching", "new", True),
    ("options_sent", "researching", True),
    ("awaiting_decision", "researching", True),
    # Invalid transitions
    ("closed", "new", False),
    ("declined", "new", False),
    ("lost", "researching", False),
    ("new", "booked", False),
    ("new", "closed", False),
    ("booked", "new", False),
    ("researching", "booked", False),
    ("researching", "awaiting_decision", False),
    # Nonsense status
    ("nonexistent", "new", False),
    ("new", "nonexistent", False),
])
def test_is_valid_workflow_transition(current, new, expected):
    assert is_valid_workflow_transition(current, new) is expected


# ── Board endpoint column completeness ───────────────────────────────────────

def test_board_includes_all_workflow_statuses():
    """The board endpoint must include ALL workflow statuses as keys, even empty ones."""
    r = http_client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    columns = r.json()["columns"]
    for status in WORKFLOW_STATUSES:
        assert status in columns, (
            f"Board columns missing workflow status '{status}' "
            f"(expected all of {sorted(WORKFLOW_STATUSES)})"
        )


def test_board_terminal_columns_present_and_empty_by_default():
    """Terminal statuses (closed, declined, lost) appear in columns even when empty."""
    r = http_client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    columns = r.json()["columns"]
    for terminal in ("closed", "declined", "lost"):
        assert terminal in columns
        assert columns[terminal] == [], f"Column '{terminal}' should be empty with no trips"


def test_board_booked_column_present():
    """'booked' column must exist in the board response."""
    r = http_client.get("/api/admin/board", headers=AUTH)
    assert r.status_code == 200
    assert "booked" in r.json()["columns"]
