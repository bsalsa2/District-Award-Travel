import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    Client, SavingsRecord, FunnelEvent,
    calc_gross_savings, calc_fee,
    PROOF_MIN_SAVINGS_CENTS, PROOF_MIN_TRIPS, PROOF_MIN_CPP_RECORDS,
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


client = TestClient(app)

ADMIN_TOKEN = make_token("admin@test.com", "admin")
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

CLIENT_NAME = "Zelda Proofcheck"
CLIENT_EMAIL = "zelda.proofcheck@example.com"


@pytest.fixture(autouse=True)
def clean_db():
    # Other test modules set this override at import time; pin ours per-test
    # and restore afterwards so module ordering never matters.
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    db.query(SavingsRecord).delete()
    db.query(FunnelEvent).delete()
    db.query(Client).delete()
    db.commit()
    db.close()
    yield
    if prev is not None:
        app.dependency_overrides[get_db] = prev
    else:
        app.dependency_overrides.pop(get_db, None)


def _seed_client(db):
    c = Client(email=CLIENT_EMAIL, password_hash=hash_pw("pw"), name=CLIENT_NAME)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _seed_record(db, client_id, label="IAD → Lisbon · Business", cash=200000,
                 taxes=10000, other=0, points=50000, status="paid"):
    r = SavingsRecord(
        client_id=client_id, trip_label=label,
        cash_benchmark_cents=cash, award_taxes_fees_cents=taxes,
        other_out_of_pocket_cents=other, points_used=points,
        fee_rate_bps=1000, status=status,
    )
    db.add(r)
    db.commit()
    return r


# ── /api/public/proof ───────────────────────────────────────────────────────
def test_proof_below_thresholds_returns_nulls():
    db = TestingSession()
    c = _seed_client(db)
    # one tiny record: below $5k savings, below 5 trips, below 3 cpp records
    _seed_record(db, c.id, cash=50000, taxes=5000, points=10000)
    db.close()
    resp = client.get("/api/public/proof")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_savings_cents"] is None
    assert body["trips_planned"] is None
    assert body["avg_cpp_tenths"] is None


def test_proof_above_thresholds_exact_math():
    db = TestingSession()
    c = _seed_client(db)
    # 5 records, each gross = 200000 - 10000 = 190000 → total 950000 ≥ 500000
    for i in range(5):
        _seed_record(db, c.id, label=f"Trip {i}", cash=200000, taxes=10000, points=50000)
    db.close()
    resp = client.get("/api/public/proof")
    body = resp.json()
    assert body["total_savings_cents"] == 5 * 190000
    assert body["trips_planned"] == 5
    # avg cpp = (950000 * 1000) // 250000 = 3800 tenths
    assert body["avg_cpp_tenths"] == (5 * 190000 * 1000) // (5 * 50000)


def test_proof_excludes_void_and_draft():
    db = TestingSession()
    c = _seed_client(db)
    _seed_record(db, c.id, status="void", cash=10000000)
    _seed_record(db, c.id, status="draft", cash=10000000)
    db.close()
    body = client.get("/api/public/proof").json()
    assert body["total_savings_cents"] is None
    assert body["trips_planned"] is None


# ── /api/public/examples ────────────────────────────────────────────────────
def test_examples_empty_db_returns_4_illustrative():
    resp = client.get("/api/public/examples")
    rows = resp.json()
    assert len(rows) == 4
    assert all(r["real"] is False for r in rows)
    for r in rows:
        gross = r["cash_cents"] - r["out_of_pocket_cents"]
        assert r["savings_cents"] == gross
        assert r["fee_cents"] == calc_fee(gross, 1000)
        assert r["net_win_cents"] == gross - r["fee_cents"]


def test_examples_real_rows_first_and_no_pii():
    db = TestingSession()
    c = _seed_client(db)
    _seed_record(db, c.id, label="IAD → Rome · Business", status="booked")
    _seed_record(db, c.id, label="DCA → Denver · Economy", status="invoiced")
    db.close()
    resp = client.get("/api/public/examples")
    rows = resp.json()
    assert len(rows) == 6  # 2 real + 4 illustrative
    assert rows[0]["real"] is True and rows[1]["real"] is True
    assert all(r["real"] is False for r in rows[2:])
    raw = resp.text
    assert CLIENT_NAME not in raw
    assert "Zelda" not in raw
    assert CLIENT_EMAIL not in raw
    # real row math
    real = rows[0]
    gross = calc_gross_savings(200000, 10000, 0)
    assert real["savings_cents"] == gross
    assert real["fee_cents"] == calc_fee(gross, 1000)


def test_examples_skips_unqualified_real_rows():
    db = TestingSession()
    c = _seed_client(db)
    _seed_record(db, c.id, label="", status="paid")          # no label
    _seed_record(db, c.id, label="X", points=0, status="paid")  # no points
    db.close()
    rows = client.get("/api/public/examples").json()
    assert all(r["real"] is False for r in rows)


# ── /api/track ──────────────────────────────────────────────────────────────
def test_track_rejects_bad_event():
    resp = client.post("/api/track", json={"event": "evil_event", "session_id": "abc"})
    assert resp.status_code == 422


def test_track_writes_row():
    resp = client.post("/api/track", json={
        "event": "page_view", "session_id": "sid-123", "page": "index",
        "utm_source": "ig",
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    db = TestingSession()
    rows = db.query(FunnelEvent).filter(FunnelEvent.session_id == "sid-123").all()
    db.close()
    assert len(rows) == 1
    assert rows[0].event == "page_view"
    assert rows[0].utm_source == "ig"


# ── /api/admin/funnel ───────────────────────────────────────────────────────
def test_funnel_requires_auth():
    assert client.get("/api/admin/funnel").status_code == 401


def test_funnel_aggregates_weeks():
    client.post("/api/track", json={"event": "page_view", "session_id": "s1", "page": "index"})
    client.post("/api/track", json={"event": "form_start", "session_id": "s1", "page": "intake"})
    client.post("/api/track", json={"event": "submit", "session_id": "s1", "utm_source": "tiktok"})
    resp = client.get("/api/admin/funnel", headers=AUTH)
    assert resp.status_code == 200
    weeks = resp.json()["weeks"]
    assert len(weeks) == 1
    w = weeks[0]
    assert w["page_view"] == 1 and w["form_start"] == 1 and w["submit"] == 1
    assert w["submits_by_utm_source"] == {"tiktok": 1}


# ── intake consent + funnel submit event ───────────────────────────────────
def test_intake_stores_consent_and_funnel_event():
    resp = client.post("/api/intake", json={
        "first_name": "Intake", "last_name": "Tester",
        "email": "intake.consent@example.com",
        "consent": "true", "_session_id": "sess-intake-1",
        "utm_source": "newsletter",
    })
    assert resp.status_code == 200
    db = TestingSession()
    from backend.main import Intake
    rec = db.query(Intake).filter(Intake.email == "intake.consent@example.com").first()
    assert rec is not None
    assert rec.consent_at is not None
    import json as _json
    assert "_session_id" not in _json.loads(rec.payload)
    ev = db.query(FunnelEvent).filter(FunnelEvent.session_id == "sess-intake-1").first()
    db.close()
    assert ev is not None and ev.event == "submit" and ev.utm_source == "newsletter"
