from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app, Base, get_db, ErrorLog

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


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body


def test_request_id_header_present():
    r = client.get("/api/health")
    assert "X-Request-ID" in r.headers
    assert len(r.headers["X-Request-ID"]) == 12


def test_unhandled_error_returns_clean_500_with_request_id():
    # register a route that blows up, hit it, confirm the middleware shields it
    @app.get("/api/_test_boom")
    def _boom():
        raise RuntimeError("test explosion")

    r = client.get("/api/_test_boom")
    assert r.status_code == 500
    body = r.json()
    assert "request_id" in body
    assert "test explosion" not in body["detail"]  # no internals leaked to client
    # remove the test route so it can't linger
    app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/api/_test_boom"]


def test_error_log_model_roundtrip():
    db = TestingSession()
    db.add(ErrorLog(request_id="abc123", route="/x", method="GET", message="m", traceback="tb"))
    db.commit()
    row = db.query(ErrorLog).filter(ErrorLog.request_id == "abc123").first()
    assert row is not None and row.route == "/x"
    db.close()
