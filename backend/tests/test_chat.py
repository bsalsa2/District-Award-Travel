"""Two-way chat: client ↔ advisor messaging endpoints.

Covers: auth on every endpoint, message persistence + flags
(unread / unread_admin), validation bounds, inbox shape, read-marking.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import (
    app, Base, get_db,
    Client,
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
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

CHAT_EMAIL = "chatty.mcchat@example.com"
CLIENT_TOKEN = make_token(CHAT_EMAIL, "client")
CLIENT_AUTH = {"Authorization": f"Bearer {CLIENT_TOKEN}"}


@pytest.fixture(autouse=True)
def clean_db():
    # Other test modules set this override at import time; pin ours per-test
    # and restore afterwards so module ordering never matters.
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    db.query(Client).delete()
    db.commit()
    db.close()
    yield
    if prev is not None:
        app.dependency_overrides[get_db] = prev
    else:
        app.dependency_overrides.pop(get_db, None)


def _seed_client(messages=None):
    db = TestingSession()
    c = Client(
        email=CHAT_EMAIL, password_hash=hash_pw("pw"), name="Chatty McChat",
        data=json.dumps({"messages": messages or []}),
    )
    db.add(c)
    db.commit()
    db.close()


def _stored_messages():
    db = TestingSession()
    c = db.query(Client).filter(Client.email == CHAT_EMAIL).first()
    msgs = json.loads(c.data or "{}").get("messages", [])
    db.close()
    return msgs


# ── POST /api/client/message ────────────────────────────────────────────────
def test_client_message_requires_auth():
    r = client.post("/api/client/message", json={"body": "hi"})
    assert r.status_code in (401, 403)


def test_client_message_rejects_admin_token():
    _seed_client()
    r = client.post("/api/client/message", json={"body": "hi"}, headers=ADMIN_AUTH)
    assert r.status_code == 403


def test_client_message_persists_with_flags():
    _seed_client()
    r = client.post("/api/client/message", json={"body": "Can you help me book?"}, headers=CLIENT_AUTH)
    assert r.status_code == 200
    msgs = _stored_messages()
    assert len(msgs) == 1
    assert msgs[0]["sender"] == "client"
    assert msgs[0]["text"] == "Can you help me book?"
    assert msgs[0]["unread_admin"] is True


def test_client_message_empty_rejected():
    _seed_client()
    r = client.post("/api/client/message", json={"body": "   "}, headers=CLIENT_AUTH)
    assert r.status_code == 422


def test_client_message_too_long_rejected():
    _seed_client()
    r = client.post("/api/client/message", json={"body": "x" * 5001}, headers=CLIENT_AUTH)
    assert r.status_code == 422


# ── POST /api/client/messages/read ──────────────────────────────────────────
def test_client_mark_read_requires_auth():
    r = client.post("/api/client/messages/read")
    assert r.status_code in (401, 403)


def test_client_mark_read_clears_advisor_unread_only():
    _seed_client(messages=[
        {"sender": "advisor", "text": "options ready", "unread": True, "time": "2026-06-01T00:00:00"},
        {"sender": "client", "text": "thanks!", "unread_admin": True, "time": "2026-06-02T00:00:00"},
    ])
    r = client.post("/api/client/messages/read", headers=CLIENT_AUTH)
    assert r.status_code == 200
    msgs = _stored_messages()
    assert msgs[0]["unread"] is False           # advisor msg now read by client
    assert msgs[1]["unread_admin"] is True      # client msg still unread by admin


# ── GET /api/admin/inbox ────────────────────────────────────────────────────
def test_inbox_requires_admin():
    assert client.get("/api/admin/inbox").status_code in (401, 403)
    assert client.get("/api/admin/inbox", headers=CLIENT_AUTH).status_code == 403


def test_inbox_shape_and_unread_count():
    _seed_client(messages=[
        {"sender": "advisor", "text": "welcome", "time": "2026-06-01T00:00:00"},
        {"sender": "client", "text": "hi there", "unread_admin": True, "time": "2026-06-02T00:00:00"},
    ])
    r = client.get("/api/admin/inbox", headers=ADMIN_AUTH)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["email"] == CHAT_EMAIL
    assert row["unread"] == 1
    assert row["last"]["sender"] == "client"
    assert row["last"]["text"] == "hi there"


# ── POST /api/admin/clients/{email}/messages/read ───────────────────────────
def test_admin_mark_read_requires_admin():
    _seed_client()
    r = client.post(f"/api/admin/clients/{CHAT_EMAIL}/messages/read")
    assert r.status_code in (401, 403)
    r = client.post(f"/api/admin/clients/{CHAT_EMAIL}/messages/read", headers=CLIENT_AUTH)
    assert r.status_code == 403


def test_admin_mark_read_clears_client_unread_only():
    _seed_client(messages=[
        {"sender": "client", "text": "hi", "unread_admin": True, "time": "2026-06-01T00:00:00"},
        {"sender": "advisor", "text": "hello!", "unread": True, "time": "2026-06-02T00:00:00"},
    ])
    r = client.post(f"/api/admin/clients/{CHAT_EMAIL}/messages/read", headers=ADMIN_AUTH)
    assert r.status_code == 200
    msgs = _stored_messages()
    assert msgs[0]["unread_admin"] is False     # client msg now read by admin
    assert msgs[1]["unread"] is True            # advisor msg still unread by client


# ── Round trip: admin reply lands in the same thread, tagged + unread ───────
def test_admin_reply_tagged_advisor_and_unread_for_client():
    _seed_client()
    r = client.post("/api/admin/send-message", headers=ADMIN_AUTH, json={
        "client_email": CHAT_EMAIL, "subject": "", "body": "Happy to help you book!",
    })
    assert r.status_code == 200
    msgs = _stored_messages()
    assert msgs[-1]["sender"] == "advisor"
    assert msgs[-1]["unread"] is True
