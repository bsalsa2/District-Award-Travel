from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as m
from backend.main import app, Base, get_db, EmailLog, _send_with_retry

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
client = TestClient(app, raise_server_exceptions=False)

NO_SLEEP = lambda s: None


def _make_log_row():
    db = TestingSession()
    row = EmailLog(recipient="x@example.com", subject="t", status="pending", attempts=0)
    db.add(row)
    db.commit()
    log_id = row.id
    db.close()
    return log_id


def _get_row(log_id):
    db = TestingSession()
    row = db.query(EmailLog).filter(EmailLog.id == log_id).first()
    db.expunge(row)
    db.close()
    return row


def test_retry_then_success(monkeypatch):
    calls = {"n": 0}

    def flaky(to, subject, body, reply_to=""):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"smtp fail {calls['n']}")

    monkeypatch.setattr(m, "_email_transport", flaky)
    log_id = _make_log_row()
    ok = _send_with_retry(log_id, "x@example.com", "t", "b",
                          sleep_fn=NO_SLEEP, session_factory=TestingSession)
    assert ok is True
    assert calls["n"] == 3
    row = _get_row(log_id)
    assert row.status == "sent"
    assert row.attempts == 3


def test_permanent_failure_never_raises(monkeypatch):
    def always_fails(to, subject, body, reply_to=""):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(m, "_email_transport", always_fails)
    log_id = _make_log_row()
    ok = _send_with_retry(log_id, "x@example.com", "t", "b",
                          sleep_fn=NO_SLEEP, session_factory=TestingSession)
    assert ok is False  # returned, did not raise
    row = _get_row(log_id)
    assert row.status == "failed"
    assert row.attempts == 3
    assert "smtp down" in row.last_error


def test_first_try_success(monkeypatch):
    monkeypatch.setattr(m, "_email_transport", lambda *a, **k: None)
    log_id = _make_log_row()
    ok = _send_with_retry(log_id, "x@example.com", "t", "b",
                          sleep_fn=NO_SLEEP, session_factory=TestingSession)
    assert ok is True
    row = _get_row(log_id)
    assert row.status == "sent"
    assert row.attempts == 1


def test_email_log_endpoint_requires_auth():
    r = client.get("/api/admin/email-log")
    assert r.status_code == 401
