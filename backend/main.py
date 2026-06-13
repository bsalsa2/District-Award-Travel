"""
District Award Travel — Backend API
====================================
A single, self-contained FastAPI application that powers:
  - Intake form submissions (stored in DB + emailed to you)
  - Client authentication (clients log into their portal)
  - Admin authentication (you log into the admin dashboard)
  - Client management (create/list clients from the admin)
  - Serving the static website (index, intake, client, admin pages)

Designed to deploy on Render's free tier with a free PostgreSQL database.
Falls back to a local SQLite file when DATABASE_URL is not set, so it also
runs on your laptop with zero setup.

Environment variables (set these in Render → Environment):
  SECRET_KEY            random long string for signing login tokens
  ADMIN_EMAIL           your admin login email (e.g. braden@districtawardtravel.com)
  ADMIN_PASSWORD        your admin login password (only used to seed the admin once)
  DATABASE_URL          provided automatically by Render Postgres (optional locally)
  GMAIL_USER            districtawardtravel@gmail.com
  GMAIL_APP_PASSWORD    16-char Google App Password (NOT your normal password)
  NOTIFY_EMAIL          where intake notifications go (defaults to GMAIL_USER)
"""

import os
import json
import secrets
import hmac
import urllib.parse
from zoneinfo import ZoneInfo
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import bcrypt
import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

try:
    from backend import ai_client
except ImportError:  # running as a flat module (uvicorn main:app)
    import ai_client
AIUnavailable = ai_client.AIUnavailable

# ──────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────
# Render gives a postgres:// URL; SQLAlchemy needs postgresql://
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
IS_PRODUCTION = bool(DATABASE_URL)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./dat.db"

# Explicit environment name. Anything with a real DATABASE_URL defaults to
# "production" — staging must OPT IN via ENV=staging. Safe-by-default: a
# service that forgets the var gets production behavior (strict secrets,
# seed scripts refuse to run).
ENV = os.environ.get("ENV", "production" if IS_PRODUCTION else "development")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@districtawardtravel.com").lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# In production (real database), secrets MUST come from the environment.
# Refusing to start beats running with forgeable tokens or a guessable admin password.
if IS_PRODUCTION:
    _missing = [n for n, v in (("SECRET_KEY", SECRET_KEY), ("ADMIN_PASSWORD", ADMIN_PASSWORD)) if not v]
    if _missing:
        raise RuntimeError(
            f"Refusing to start: missing required env vars in production: {', '.join(_missing)}. "
            "Set them in the Render dashboard (Environment tab)."
        )
else:
    # Local dev: ephemeral key (tokens won't survive restarts — fine for dev) and a dev password.
    import secrets as _secrets
    SECRET_KEY = SECRET_KEY or _secrets.token_hex(32)
    ADMIN_PASSWORD = ADMIN_PASSWORD or "dev-only-password"

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24 * 7  # one week

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", GMAIL_USER or "districtawardtravel@gmail.com")

# Public proof thresholds — stats only shown once they clear these floors
PROOF_MIN_SAVINGS_CENTS = int(os.environ.get("PROOF_MIN_SAVINGS_CENTS", "500000"))  # $5,000
PROOF_MIN_TRIPS = int(os.environ.get("PROOF_MIN_TRIPS", "5"))
PROOF_MIN_CPP_RECORDS = int(os.environ.get("PROOF_MIN_CPP_RECORDS", "3"))

BASE_URL = os.environ.get("BASE_URL", "https://district-award-travel.onrender.com")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SEATS_AERO_API_KEY = os.environ.get("SEATS_AERO_API_KEY", "")

# Path to the static website files
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.normpath(os.path.join(HERE, "..", "platform", "public"))

# ──────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# Pool pinned for Render free Postgres (~95 usable connections, 1 web instance):
# 5 persistent + 5 overflow = hard cap of 10 from this process. pool_recycle
# beats Render's idle-connection reaping; pre_ping catches the stragglers.
engine = create_engine(
    DATABASE_URL, connect_args=connect_args, pool_pre_ping=True,
    pool_size=5, max_overflow=5, pool_recycle=300, pool_timeout=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, default="Admin")
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    tier = Column(String, default="Client")
    # Full portal payload (trips, savings, points, messages) stored as JSON text
    data = Column(Text, default="{}")
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Intake(Base):
    __tablename__ = "intakes"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    email = Column(String, default="", index=True)
    phone = Column(String, default="")
    payload = Column(Text, default="{}")  # complete raw submission
    consent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class FunnelEvent(Base):
    __tablename__ = "funnel_events"
    id         = Column(Integer, primary_key=True)
    session_id = Column(String, default="", index=True)
    event      = Column(String, nullable=False, index=True)   # page_view|form_start|step_1_complete|step_2_complete|step_3_complete|submit
    page       = Column(String, default="")
    utm_source = Column(String, default="")
    utm_medium = Column(String, default="")
    utm_campaign = Column(String, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)


class SavingsRecord(Base):
    __tablename__ = "savings_records"
    id                        = Column(Integer, primary_key=True)
    client_id                 = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    trip_label                = Column(String, default="")
    cash_benchmark_cents      = Column(Integer, nullable=False)
    benchmark_source          = Column(String, default="")
    benchmark_captured_at     = Column(DateTime, nullable=True)
    benchmark_screenshot      = Column(Text, default="")
    benchmark_assumptions     = Column(Text, default="")
    option_booked             = Column(Text, default="")
    points_used               = Column(Integer, default=0)
    points_program            = Column(String, default="")
    award_taxes_fees_cents    = Column(Integer, default=0)
    other_out_of_pocket_cents = Column(Integer, default=0)
    fee_rate_bps              = Column(Integer, default=1000)
    status                    = Column(String, default="draft", index=True)
    invoice_number            = Column(String, default="")
    invoiced_at               = Column(DateTime, nullable=True)
    paid_at                   = Column(DateTime, nullable=True)
    payment_method            = Column(String, default="")
    notes                     = Column(Text, default="")
    report_token              = Column(String, default="", index=True)
    created_at                = Column(DateTime, default=dt.datetime.utcnow)
    updated_at                = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class TripRequest(Base):
    __tablename__ = "trip_requests"
    id                   = Column(Integer, primary_key=True)
    client_id            = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    destination          = Column(String, default="")
    origin               = Column(String, default="")
    dates                = Column(String, default="")
    passengers           = Column(String, default="1")
    cabin                = Column(String, default="")
    flexibility          = Column(String, default="")
    workflow_status      = Column(String, default="new", index=True)
    stage_entered_at     = Column(DateTime, default=dt.datetime.utcnow)
    last_activity_at     = Column(DateTime, default=dt.datetime.utcnow)
    savings_record_id    = Column(Integer, ForeignKey("savings_records.id"), nullable=True)
    time_tracked_minutes = Column(Integer, default=0)
    notes                = Column(Text, default="[]")
    research_notes       = Column(Text, default="")
    created_at           = Column(DateTime, default=dt.datetime.utcnow)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    id          = Column(Integer, primary_key=True)
    trip_id     = Column(Integer, ForeignKey("trip_requests.id"), nullable=False, index=True)
    from_status = Column(String, default="")
    to_status   = Column(String, nullable=False)
    note        = Column(Text, default="")
    created_at  = Column(DateTime, default=dt.datetime.utcnow)


class ResearchTemplate(Base):
    __tablename__ = "research_templates"
    id          = Column(Integer, primary_key=True)
    program     = Column(String, nullable=False)
    portal_name = Column(String, nullable=False)
    portal_url  = Column(String, default="")
    sort_order  = Column(Integer, default=0)
    active      = Column(Integer, default=1)


class Snippet(Base):
    __tablename__ = "snippets"
    id         = Column(Integer, primary_key=True)
    title      = Column(String, nullable=False)
    body       = Column(Text, default="")
    category   = Column(String, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class MessageTemplate(Base):
    __tablename__ = "message_templates"
    id         = Column(Integer, primary_key=True)
    category   = Column(String, default="")
    title      = Column(String, nullable=False)
    subject    = Column(String, default="")
    body       = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class EmailLog(Base):
    __tablename__ = "email_log"
    id         = Column(Integer, primary_key=True)
    recipient  = Column(String, default="")
    subject    = Column(String, default="")
    status     = Column(String, default="pending", index=True)  # pending|sent|failed
    attempts   = Column(Integer, default=0)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class ErrorLog(Base):
    __tablename__ = "error_log"
    id         = Column(Integer, primary_key=True)
    request_id = Column(String, default="", index=True)
    route      = Column(String, default="")
    method     = Column(String, default="")
    message    = Column(Text, default="")
    traceback  = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    id                = Column(Integer, primary_key=True)
    provider          = Column(String, nullable=False, index=True)
    operation         = Column(String, default="")
    latency_ms        = Column(Integer, default=0)
    success           = Column(Integer, default=1)
    error             = Column(Text, default="")
    est_cost_microusd = Column(Integer, default=0)
    created_at        = Column(DateTime, default=dt.datetime.utcnow)


Base.metadata.create_all(bind=engine)

# Additive migration: create_all doesn't add columns to existing tables.
try:
    from sqlalchemy import text as _sql_text
    with engine.begin() as _conn:
        _conn.execute(_sql_text("ALTER TABLE intakes ADD COLUMN consent_at TIMESTAMP"))
except Exception:
    pass  # column already exists (or fresh DB where create_all included it)

try:
    from sqlalchemy import text as _sql_text_rn
    with engine.begin() as _conn:
        _conn.execute(_sql_text_rn("ALTER TABLE trip_requests ADD COLUMN research_notes TEXT DEFAULT ''"))
except Exception:
    pass  # column already exists (or fresh DB where create_all included it)

# Index migration: create_all skips existing tables entirely, so indexes added
# after a table first shipped must be created explicitly. IF NOT EXISTS works
# on both Postgres and SQLite. Rollback for each: DROP INDEX <name>.
_INDEX_MIGRATIONS = [
    "CREATE INDEX IF NOT EXISTS ix_intakes_created_at ON intakes (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_savings_records_invoice_number ON savings_records (invoice_number)",
    "CREATE INDEX IF NOT EXISTS ix_workflow_events_created_at ON workflow_events (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_trip_requests_savings_record_id ON trip_requests (savings_record_id)",
]
try:
    from sqlalchemy import text as _sql_text2
    with engine.begin() as _conn:
        for _stmt in _INDEX_MIGRATIONS:
            _conn.execute(_sql_text2(_stmt))
except Exception as _e:
    print(f"[startup] index migration warning: {_e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────────────
# Security helpers
# ──────────────────────────────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(subject: str, role: str) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": dt.datetime.utcnow() + dt.timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


bearer = HTTPBearer(auto_error=False)


def current_identity(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_admin(identity: dict = Depends(current_identity)) -> dict:
    if identity.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return identity


# ──────────────────────────────────────────────────────────────────────────
# Savings formulas — integer math only, no floats
# ──────────────────────────────────────────────────────────────────────────
VALID_STATUS_TRANSITIONS = {
    "draft":     {"presented", "void"},
    "presented": {"booked", "draft", "void"},
    "booked":    {"invoiced", "void"},
    "invoiced":  {"paid", "void"},
    "paid":      {"void"},
    "void":      set(),
}
VALID_STATUSES = set(VALID_STATUS_TRANSITIONS.keys())


def calc_gross_savings(cash_benchmark_cents: int, award_taxes_fees_cents: int, other_out_of_pocket_cents: int) -> int:
    return cash_benchmark_cents - award_taxes_fees_cents - other_out_of_pocket_cents


def calc_fee(gross_savings_cents: int, fee_rate_bps: int) -> int:
    """Round half-up via +5000 before integer division by 10000."""
    if gross_savings_cents <= 0:
        return 0
    return (gross_savings_cents * fee_rate_bps + 5000) // 10000


def calc_cpp_tenths(gross_savings_cents: int, points_used: int) -> int:
    """Cents-per-point * 10, integer. Returns 0 if points_used == 0."""
    if points_used <= 0:
        return 0
    return (gross_savings_cents * 1000) // points_used


def is_valid_transition(current_status: str, new_status: str) -> bool:
    return new_status in VALID_STATUS_TRANSITIONS.get(current_status, set())


# ──────────────────────────────────────────────────────────────────────────
# Workflow logic
# ──────────────────────────────────────────────────────────────────────────
WORKFLOW_TRANSITIONS = {
    "new":               {"researching", "declined", "lost"},
    "researching":       {"options_sent", "new", "declined", "lost"},
    "options_sent":      {"awaiting_decision", "researching", "declined", "lost"},
    "awaiting_decision": {"booked", "researching", "declined", "lost"},
    "booked":            {"closed"},
    "closed":            set(),
    "declined":          set(),
    "lost":              set(),
}
WORKFLOW_STATUSES = set(WORKFLOW_TRANSITIONS.keys())
REASON_REQUIRED_STATUSES = {"declined", "lost"}


def is_valid_workflow_transition(current: str, new: str) -> bool:
    return new in WORKFLOW_TRANSITIONS.get(current, set())


def trip_attention_flags(workflow_status: str, stage_entered_at, last_activity_at, now=None) -> dict:
    now = now or dt.datetime.utcnow()
    hours = int((now - stage_entered_at).total_seconds() // 3600) if stage_entered_at else 0
    level = "ok"
    follow_up = False
    if workflow_status == "new":
        if hours > 48:
            level = "red"
        elif hours > 24:
            level = "amber"
    elif workflow_status == "researching":
        if hours > 48:
            level = "red"
        elif hours > 24:
            level = "amber"
    elif workflow_status == "options_sent":
        idle_hours = int((now - last_activity_at).total_seconds() // 3600) if last_activity_at else hours
        if idle_hours > 72:
            follow_up = True
            level = "amber"
    return {"level": level, "follow_up": follow_up, "hours_in_stage": hours}


import re as _re
def render_template(body: str, variables: dict) -> str:
    def replacer(m):
        key = m.group(1)
        return str(variables[key]) if key in variables else m.group(0)
    return _re.sub(r"\{(\w+)\}", replacer, body)


def _trip_row(trip: TripRequest, client=None, now=None) -> dict:
    flags = trip_attention_flags(trip.workflow_status, trip.stage_entered_at, trip.last_activity_at, now)
    row = {
        "id": trip.id,
        "client_id": trip.client_id,
        "destination": trip.destination,
        "origin": trip.origin,
        "dates": trip.dates,
        "passengers": trip.passengers,
        "cabin": trip.cabin,
        "flexibility": trip.flexibility,
        "workflow_status": trip.workflow_status,
        "stage_entered_at": trip.stage_entered_at.isoformat() if trip.stage_entered_at else None,
        "last_activity_at": trip.last_activity_at.isoformat() if trip.last_activity_at else None,
        "savings_record_id": trip.savings_record_id,
        "time_tracked_minutes": trip.time_tracked_minutes,
        "notes": json.loads(trip.notes or "[]"),
        "research_notes": trip.research_notes or "",
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        **flags,
        "stale": flags.get("level") != "ok" and trip.workflow_status not in {"closed", "declined", "lost", "booked"},
    }
    if client:
        row["client_name"] = client.name
        row["client_email"] = client.email
        cdata = json.loads(client.data or "{}")
        row["programs"] = [p.get("program", "") for p in cdata.get("points", [])]
    return row


def _savings_row(rec: SavingsRecord) -> dict:
    gross = calc_gross_savings(rec.cash_benchmark_cents, rec.award_taxes_fees_cents, rec.other_out_of_pocket_cents)
    fee = calc_fee(gross, rec.fee_rate_bps)
    cpp = calc_cpp_tenths(gross, rec.points_used)
    return {
        "id": rec.id,
        "client_id": rec.client_id,
        "trip_label": rec.trip_label,
        "cash_benchmark_cents": rec.cash_benchmark_cents,
        "benchmark_source": rec.benchmark_source,
        "benchmark_captured_at": rec.benchmark_captured_at.isoformat() if rec.benchmark_captured_at else None,
        "benchmark_assumptions": rec.benchmark_assumptions,
        "benchmark_screenshot": rec.benchmark_screenshot,
        "option_booked": rec.option_booked,
        "points_used": rec.points_used,
        "points_program": rec.points_program,
        "award_taxes_fees_cents": rec.award_taxes_fees_cents,
        "other_out_of_pocket_cents": rec.other_out_of_pocket_cents,
        "fee_rate_bps": rec.fee_rate_bps,
        "gross_savings_cents": gross,
        "fee_cents": fee,
        "cpp_tenths": cpp,
        "status": rec.status,
        "invoice_number": rec.invoice_number,
        "invoiced_at": rec.invoiced_at.isoformat() if rec.invoiced_at else None,
        "paid_at": rec.paid_at.isoformat() if rec.paid_at else None,
        "payment_method": rec.payment_method,
        "notes": rec.notes,
        "report_token": rec.report_token,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


# ──────────────────────────────────────────────────────────────────────────
# Email — single interface, async with retry, logged to email_log.
# A failed email must NEVER fail the request that triggered it. The
# transport is swappable (EMAIL_PROVIDER env) so moving to a transactional
# provider later is config + one function, not a refactor.
# ──────────────────────────────────────────────────────────────────────────
import threading as _threading

EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "gmail")
EMAIL_RETRY_DELAYS = [5, 25]  # seconds between attempts (3 attempts total)


def _smtp_transport(to: str, subject: str, body: str, reply_to: str = "") -> None:
    """Gmail SMTP transport. Raises on failure (retry logic lives above it)."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_USER / GMAIL_APP_PASSWORD not set")
    msg = MIMEMultipart()
    msg["From"] = f"District Award Travel <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    mime_subtype = "html" if body.lstrip().startswith("<") else "plain"
    msg.attach(MIMEText(body, mime_subtype))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [to], msg.as_string())


_email_transport = _smtp_transport  # seam for tests / future providers


def _send_with_retry(log_id: int, to: str, subject: str, body: str,
                     reply_to: str = "", sleep_fn=None, session_factory=None) -> bool:
    """Attempt delivery up to 3 times with backoff, recording every attempt
    on the email_log row. Never raises."""
    import time as _t
    sleep_fn = sleep_fn or _t.sleep
    session_factory = session_factory or SessionLocal

    def _update(status: str, attempts: int, err: str):
        try:
            db = session_factory()
            try:
                row = db.query(EmailLog).filter(EmailLog.id == log_id).first()
                if row:
                    row.status = status
                    row.attempts = attempts
                    row.last_error = err[:1000]
                    row.updated_at = dt.datetime.utcnow()
                    db.commit()
            finally:
                db.close()
        except Exception:
            pass  # logging must never break sending

    last_err = ""
    for attempt in range(1, len(EMAIL_RETRY_DELAYS) + 2):
        try:
            _email_transport(to, subject, body, reply_to)
            _update("sent", attempt, "")
            return True
        except Exception as e:
            last_err = str(e)
            if attempt <= len(EMAIL_RETRY_DELAYS):
                _update("pending", attempt, last_err)
                sleep_fn(EMAIL_RETRY_DELAYS[attempt - 1])
    _update("failed", len(EMAIL_RETRY_DELAYS) + 1, last_err)
    print(f"[email] giving up after {len(EMAIL_RETRY_DELAYS) + 1} attempts to {to}: {last_err}")
    return False


def queue_email(to: str, subject: str, body: str, reply_to: str = "") -> bool:
    """The ONE way to send email. Creates an email_log row and delivers from
    a daemon thread (with retries) so the calling request returns instantly.
    Returns True = queued (delivery status lives in email_log)."""
    if not to:
        return False
    try:
        db = SessionLocal()
        try:
            row = EmailLog(recipient=to, subject=subject[:300], status="pending", attempts=0)
            db.add(row)
            db.commit()
            log_id = row.id
        finally:
            db.close()
    except Exception as e:
        print(f"[email] could not create email_log row: {e}")
        return False
    _threading.Thread(
        target=_send_with_retry, args=(log_id, to, subject, body, reply_to), daemon=True
    ).start()
    return True


def send_email(subject: str, body: str, reply_to: str = "") -> bool:
    """Queue a plain-text email to the admin notify address."""
    return queue_email(NOTIFY_EMAIL, subject, body, reply_to=reply_to)


def send_email_to(to: str, subject: str, body: str, reply_to: str = "") -> bool:
    """Queue a plain-text email to any address (kept for existing call sites)."""
    return queue_email(to, subject, body, reply_to=reply_to)


# Status-specific client notification config
_CLIENT_STATUS_EMAILS = {
    "options_sent": {
        "subject": "Your travel options are ready!",
        "message": "Your advisor has sent travel options for your trip to {destination}. Log in to review them.",
    },
    "booked": {
        "subject": "Your trip has been booked! 🎉",
        "message": "Great news! Your trip to {destination} has been booked. Check your portal for details.",
    },
}


def _notify_client_status_change(client_email: str, client_name: str, destination: str, new_status: str) -> None:
    """Send a branded HTML notification email to the client when a trip reaches a notable status.
    Swallows all exceptions so the caller's workflow is never interrupted."""
    cfg = _CLIENT_STATUS_EMAILS.get(new_status)
    if not cfg:
        return
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return
    if not client_email:
        return
    try:
        first_name = client_name.split()[0] if client_name else "there"
        portal_url = BASE_URL + "/client.html"
        message = cfg["message"].format(destination=destination or "your destination")
        body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;">
        <tr>
          <td style="background:#f97316;padding:24px 32px;">
            <span style="color:#ffffff;font-size:22px;font-weight:bold;">District Award Travel</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <p style="font-size:16px;color:#1e293b;margin:0 0 16px;">Hi {first_name},</p>
            <p style="font-size:16px;color:#1e293b;margin:0 0 24px;">{message}</p>
            <a href="{portal_url}" style="display:inline-block;background:#f97316;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:bold;">View My Portal</a>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px;border-top:1px solid #e2e8f0;">
            <p style="font-size:12px;color:#94a3b8;margin:0;text-align:center;">District Award Travel &middot; No upfront cost &middot; Proven savings</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        queue_email(client_email, cfg["subject"], body)
    except Exception as exc:
        logger.error("client_status_email.failed", extra={"status": new_status, "error": str(exc)})


def format_intake_email(data: dict) -> str:
    pts = [
        f"  {k.replace('pts_', '').replace('_', ' ').upper()}: {v}"
        for k, v in data.items()
        if k.startswith("pts_") and v
    ]
    lines = [
        "=== NEW INTAKE SUBMISSION ===",
        f"Received: {dt.datetime.utcnow().isoformat()} UTC",
        "",
        "-- CONTACT --",
        f"Name: {data.get('first_name','')} {data.get('last_name','')}",
        f"Email: {data.get('email','')}",
        f"Phone: {data.get('phone','')}",
        f"Home Airport: {data.get('home_airport','')}",
        f"Referral: {data.get('referral_source','')} / {data.get('referral_name','')}",
        "",
        "-- POINTS BALANCES --",
        "\n".join(pts) if pts else "  (none entered)",
        "",
        "-- ELITE STATUS / CARDS --",
        f"Airline: {data.get('airline_status','None')}",
        f"Hotel: {data.get('hotel_status','None')}",
        f"Amex Card: {data.get('amex_card','None')}",
        f"Chase Card: {data.get('chase_card','None')}",
        "",
        "-- TRAVEL GOALS --",
        data.get("travel_goals", ""),
        f"Trip 1: {data.get('trip1_dest','')} — {data.get('trip1_dates','')}",
        f"Trip 2: {data.get('trip2_dest','')} — {data.get('trip2_dates','')}",
        f"Trip 3: {data.get('trip3_dest','')} — {data.get('trip3_dates','')}",
        f"Cabin: {data.get('cabin_pref','')}",
        f"Hotel Tier: {data.get('hotel_tier','')}",
        "",
        "-- PREFERENCES --",
        f"Flexibility: {data.get('date_flexibility','')}",
        f"Contact Pref: {data.get('comm_pref','')}",
        f"Max Stops: {data.get('max_stops','')}",
        f"Trip Type: {data.get('trip_type','')}",
        f"Notes: {data.get('notes','')}",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────
app = FastAPI(title="District Award Travel API", version="2.0.0")
APP_VERSION = os.environ.get("RENDER_GIT_COMMIT", "dev")[:12]

# ──────────────────────────────────────────────────────────────────────────
# Observability: structured JSON logs, request middleware, slow-query log,
# error capture with email alert. Fail loudly to the operator, never to
# the client beyond a clean 500.
# ──────────────────────────────────────────────────────────────────────────
import logging
import time as _time
import traceback as _traceback
import threading as _threading
import uuid as _uuid


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": dt.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "route", "method", "status", "latency_ms", "duration_ms", "query"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry)


logger = logging.getLogger("dat")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(_JsonFormatter())
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

SLOW_QUERY_MS = int(os.environ.get("SLOW_QUERY_MS", "200"))

from sqlalchemy import event as _sa_event


@_sa_event.listens_for(engine, "before_cursor_execute")
def _before_cursor(conn, cursor, statement, parameters, context, executemany):
    context._dat_query_start = _time.perf_counter()


@_sa_event.listens_for(engine, "after_cursor_execute")
def _after_cursor(conn, cursor, statement, parameters, context, executemany):
    start = getattr(context, "_dat_query_start", None)
    if start is None:
        return
    elapsed_ms = int((_time.perf_counter() - start) * 1000)
    if elapsed_ms >= SLOW_QUERY_MS:
        logger.warning("slow query", extra={"duration_ms": elapsed_ms, "query": statement[:300]})


def _record_error(request_id: str, route: str, method: str, exc: BaseException):
    """Persist the error and email the operator. Runs in a thread so the
    (blocking, up-to-10s) SMTP send never delays the error response."""
    tb = "".join(_traceback.format_exception(type(exc), exc, exc.__traceback__))[-8000:]

    def _work():
        try:
            db = SessionLocal()
            try:
                db.add(ErrorLog(request_id=request_id, route=route, method=method,
                                message=str(exc)[:500], traceback=tb))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass  # never let error-logging cause more errors
        try:
            send_email(
                subject=f"[DAT 500] {method} {route}",
                body=f"request_id: {request_id}\nroute: {method} {route}\n\n{str(exc)[:500]}\n\n{tb}",
            )
        except Exception:
            pass

    _threading.Thread(target=_work, daemon=True).start()


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = _uuid.uuid4().hex[:12]
    start = _time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        latency_ms = int((_time.perf_counter() - start) * 1000)
        logger.error("unhandled error", extra={
            "request_id": request_id, "route": request.url.path,
            "method": request.method, "status": 500, "latency_ms": latency_ms,
        })
        _record_error(request_id, request.url.path, request.method, exc)
        return JSONResponse(status_code=500, content={
            "detail": "Something went wrong on our side. We've been notified.",
            "request_id": request_id,
        })
    latency_ms = int((_time.perf_counter() - start) * 1000)
    if not request.url.path.startswith(("/assets", "/favicon")):
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, "request", extra={
            "request_id": request_id, "route": request.url.path,
            "method": request.method, "status": response.status_code,
            "latency_ms": latency_ms,
        })
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/healthz")
def healthz():
    """Liveness + DB check for external uptime monitoring. A dead database
    must report unhealthy — a monitor pinging a static 200 proves nothing."""
    try:
        from sqlalchemy import text as _t
        with engine.connect() as conn:
            conn.execute(_t("SELECT 1"))
        return {"status": "ok", "version": APP_VERSION, "db": "ok"}
    except Exception as e:
        logger.error("healthz db failure", extra={"route": "/healthz"})
        return JSONResponse(status_code=503, content={"status": "degraded", "version": APP_VERSION, "db": f"error: {str(e)[:200]}"})

# Frontends are served from this same origin, so cross-origin access is only
# needed for explicitly listed extra origins (ALLOWED_ORIGINS, comma-separated).
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://district-award-travel.onrender.com,https://districtawardtravel.com,https://www.districtawardtravel.com",
    ).split(",") if o.strip()
]
for _local in ["http://localhost:8000", "http://127.0.0.1:8000"]:
    if _local not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(_local)

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)  # admin.html alone is >150KB


@app.middleware("http")
async def cache_headers_middleware(request: Request, call_next):
    """Immutable assets get a day of caching; HTML stays no-cache so deploys
    are visible immediately; API responses are never cached."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/") or path == "/favicon.svg":
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.endswith(".html") or path == "/":
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting: protects login endpoints from brute force and the intake
# form from spam floods (each intake also triggers outbound emails).
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def seed_phase2_defaults():
    db = SessionLocal()
    try:
        if db.query(ResearchTemplate).count() == 0:
            defaults = [
                ("Chase Ultimate Rewards", "Hyatt (1:1 transfer)", "https://world.hyatt.com/content/gp/en/awards/award-search.html", 1),
                ("Chase Ultimate Rewards", "United MileagePlus (1:1 transfer)", "https://www.united.com/en/us/book-flight/united-awards", 2),
                ("Chase Ultimate Rewards", "Air Canada Aeroplan (1:1 transfer)", "https://www.aircanada.com/aeroplan/redeem/", 3),
                ("Chase Ultimate Rewards", "Air France/KLM Flying Blue (1:1 transfer)", "https://wwws.airfrance.us/information/flying-blue", 4),
                ("Amex Membership Rewards", "ANA Mileage Club (1:1 transfer)", "https://www.ana.co.jp/en/us/amc/", 1),
                ("Amex Membership Rewards", "Air France/KLM Flying Blue (1:1 transfer)", "https://wwws.airfrance.us/information/flying-blue", 2),
                ("Amex Membership Rewards", "Avianca LifeMiles (1:1 transfer)", "https://www.lifemiles.com/", 3),
                ("Amex Membership Rewards", "Delta SkyMiles (1:1 transfer)", "https://www.delta.com/us/en/skymiles/redeem-miles/book-award-travel", 4),
                ("Capital One Miles", "Turkish Miles&Smiles (1:1 transfer)", "https://www.turkishairlines.com/en-us/miles-and-smiles/", 1),
                ("Capital One Miles", "Air Canada Aeroplan (1:1 transfer)", "https://www.aircanada.com/aeroplan/redeem/", 2),
                ("United MileagePlus", "United Award Search", "https://www.united.com/en/us/book-flight/united-awards", 1),
                ("American AAdvantage", "AA Award Search", "https://www.aa.com/homePage.do", 1),
                ("Alaska Mileage Plan", "Alaska Award Search", "https://www.alaskaair.com/content/mileage-plan/use-miles/award-travel", 1),
                ("World of Hyatt", "Hyatt Award Search", "https://world.hyatt.com/content/gp/en/awards/award-search.html", 1),
                ("Delta SkyMiles", "Delta Award Search", "https://www.delta.com/us/en/skymiles/redeem-miles/book-award-travel", 1),
            ]
            for program, portal_name, portal_url, sort_order in defaults:
                db.add(ResearchTemplate(program=program, portal_name=portal_name, portal_url=portal_url, sort_order=sort_order))
            db.commit()
        if db.query(MessageTemplate).count() == 0:
            templates = [
                ("welcome", "Welcome", "Welcome to District Award Travel!", "Hi {first_name},\n\nWelcome to District Award Travel! I'm Braden, and I'm excited to help you get the most out of your points and miles.\n\nI've reviewed your profile and I'm already thinking about some great options for your trips. I'll be in touch soon with personalized recommendations.\n\nIn the meantime, feel free to reply with any questions or updates to your travel plans.\n\nBest,\nBraden\nDistrict Award Travel"),
                ("options_ready", "Options Ready", "Your travel options are ready — {route}", "Hi {first_name},\n\nGreat news — I've put together some award options for {route} that I think you'll love.\n\nPlease log in to your portal to review the detailed options with screenshots. Once you've had a chance to look them over, let me know which direction interests you most and I'll help you get it booked.\n\nRemember: award space can disappear quickly, so don't wait too long!\n\nBest,\nBraden\nDistrict Award Travel"),
                ("nudge_72h", "72h Follow-Up Nudge", "Quick check-in on your options — {route}", "Hi {first_name},\n\nJust checking in on the options I sent over for {route}. Have you had a chance to look them over?\n\nIf you have any questions or want me to search for other options, just reply and I'll get right on it.\n\nBest,\nBraden\nDistrict Award Travel"),
                ("booking_confirmed", "Booking Confirmed", "Booking confirmed — {route}", "Hi {first_name},\n\nFantastic news — your trip is booked! Here's a quick recap:\n\nRoute: {route}\n\nYou saved {savings_amount} compared to the cash price. My fee is {fee_amount}, which I'll invoice shortly.\n\nThank you for trusting District Award Travel. I can't wait to hear about your trip!\n\nBest,\nBraden\nDistrict Award Travel"),
                ("invoice", "Invoice", "Invoice from District Award Travel — {route}", "Hi {first_name},\n\nThank you for working with District Award Travel! Please find your invoice details below:\n\nRoute: {route}\nTotal Savings: {savings_amount}\nDistrict Fee (10%): {fee_amount}\n\nPayment can be made via Venmo, Zelle, or check. Please reach out with any questions.\n\nThank you again!\n\nBraden\nDistrict Award Travel"),
                ("referral_ask", "Referral Ask", "Quick favor?", "Hi {first_name},\n\nI hope you're enjoying the fruits of your savings — {savings_amount} is nothing to sneeze at!\n\nI'm growing District Award Travel mostly through word of mouth, and if you know anyone who travels and has points sitting around, I'd love an introduction. One name is all it takes.\n\nThank you for being such a great client.\n\nBraden\nDistrict Award Travel"),
            ]
            for category, title, subject, body in templates:
                db.add(MessageTemplate(category=category, title=title, subject=subject, body=body))
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
def seed_admin():
    """Ensure the admin account matches the current env vars.

    The ADMIN_EMAIL / ADMIN_PASSWORD env vars are the single source of truth:
    if the admin doesn't exist it's created, and if it does exist its password
    is re-synced on every startup. This keeps a Render password change from
    being silently ignored just because the admin row already existed.
    """
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.email == ADMIN_EMAIL).first()
        if not existing:
            db.add(Admin(email=ADMIN_EMAIL, password_hash=hash_pw(ADMIN_PASSWORD), name="Braden Salcetti"))
            db.commit()
            print(f"[startup] Seeded admin: {ADMIN_EMAIL}")
        else:
            # Re-sync the password to whatever ADMIN_PASSWORD currently is.
            if not verify_pw(ADMIN_PASSWORD, existing.password_hash):
                existing.password_hash = hash_pw(ADMIN_PASSWORD)
                db.commit()
                print(f"[startup] Re-synced admin password for: {ADMIN_EMAIL}")
    finally:
        db.close()


# ── Schemas ──
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ClientIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    tier: str = "Client"
    data: dict = {}


class SavingsCreateIn(BaseModel):
    client_email: str
    trip_label: str = ""
    cash_benchmark_cents: int = Field(..., ge=0)
    benchmark_source: str = ""
    benchmark_captured_at: Optional[str] = None  # ISO datetime string
    benchmark_assumptions: str = ""
    benchmark_screenshot: str = ""   # base64, validated <= 1.5MB
    option_booked: str = ""
    points_used: int = Field(0, ge=0)
    points_program: str = ""
    award_taxes_fees_cents: int = Field(0, ge=0)
    other_out_of_pocket_cents: int = Field(0, ge=0)
    fee_rate_bps: int = Field(1000, ge=0, le=10000)
    notes: str = ""

class SavingsPatchIn(BaseModel):
    trip_label: Optional[str] = None
    cash_benchmark_cents: Optional[int] = Field(None, ge=0)
    benchmark_source: Optional[str] = None
    benchmark_captured_at: Optional[str] = None
    benchmark_assumptions: Optional[str] = None
    benchmark_screenshot: Optional[str] = None
    option_booked: Optional[str] = None
    points_used: Optional[int] = Field(None, ge=0)
    points_program: Optional[str] = None
    award_taxes_fees_cents: Optional[int] = Field(None, ge=0)
    other_out_of_pocket_cents: Optional[int] = Field(None, ge=0)
    fee_rate_bps: Optional[int] = Field(None, ge=0, le=10000)
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None

class StatusAdvanceIn(BaseModel):
    new_status: str
    payment_method: Optional[str] = None  # recorded when transitioning to paid


class LegacyImportIn(BaseModel):
    entries: list
    client_email: Optional[str] = None  # if omitted, falls back to admin email


class TripCreateIn(BaseModel):
    client_email: str
    destination: str = ""
    origin: str = ""
    dates: str = ""
    passengers: str = "1"
    cabin: str = ""
    flexibility: str = ""


class TripPatchIn(BaseModel):
    destination: Optional[str] = None
    origin: Optional[str] = None
    dates: Optional[str] = None
    passengers: Optional[str] = None
    cabin: Optional[str] = None
    flexibility: Optional[str] = None


class WorkflowAdvanceIn(BaseModel):
    new_status: str
    note: str = ""


class TripNoteIn(BaseModel):
    text: str


class TripResearchNotesIn(BaseModel):
    research_notes: str = Field(..., max_length=10000)


class TripTimeIn(BaseModel):
    minutes: int = Field(..., ge=1, le=600)


class LinkSavingsIn(BaseModel):
    savings_record_id: int


class SnippetIn(BaseModel):
    title: str
    body: str = ""
    category: str = ""


class SnippetPatchIn(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None


class ResearchTemplateIn(BaseModel):
    program: str
    portal_name: str
    portal_url: str = ""
    sort_order: int = 0
    active: int = 1


class ResearchTemplatePatchIn(BaseModel):
    program: Optional[str] = None
    portal_name: Optional[str] = None
    portal_url: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[int] = None


class MessageTemplateIn(BaseModel):
    category: str = ""
    title: str
    subject: str = ""
    body: str = ""


class MessageTemplatePatchIn(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class TemplateRenderIn(BaseModel):
    client_email: str
    trip_id: Optional[int] = None


ALLOWED_FUNNEL_EVENTS = {
    "page_view", "form_start",
    "step_1_complete", "step_2_complete", "step_3_complete",
    "submit",
}


class TrackIn(BaseModel):
    event: str
    session_id: str = Field("", max_length=64)
    page: str = Field("", max_length=200)
    utm_source: str = Field("", max_length=100)
    utm_medium: str = Field("", max_length=100)
    utm_campaign: str = Field("", max_length=100)

    @field_validator("event")
    @classmethod
    def _event_allowed(cls, v: str) -> str:
        if v not in ALLOWED_FUNNEL_EVENTS:
            raise ValueError("unknown event")
        return v


# ── Health ──
@app.get("/api/health")
def health():
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat()}


# ── AI: parse a raw email into structured client data ──
class ParseEmailIn(BaseModel):
    raw_email: str

EMAIL_PARSE_PROMPT = """You are an assistant for District Award Travel, a points-and-miles advisory firm.
Extract client information from the raw email below and return ONLY valid JSON — no markdown, no extra text.

JSON schema (use null for missing fields):
{
  "first_name": string|null,
  "last_name": string|null,
  "email": string|null,
  "phone": string|null,
  "home_airport": string|null,
  "travel_goals": string|null,
  "trips": [{"destination": string, "dates": string}],
  "points": [{"program": string, "balance": string}],
  "cabin_pref": string|null,
  "notes": string|null
}

Rules:
- Extract names, email addresses, phone numbers exactly as written.
- Infer home airport from any U.S. city mentioned if obvious (e.g. "DC" → DCA/IAD, "NYC" → JFK/LGA/EWR, "LA" → LAX, "Chicago" → ORD).
- Capture any mentioned points/miles programs and balances.
- Put travel goals, destinations, and any other context in the relevant fields.
- Return ONLY the JSON object, nothing else.

Raw email:
"""

@app.post("/api/ai/parse-email")
async def parse_email(body: ParseEmailIn, _: dict = Depends(require_admin)):
    """Use Groq (llama-3.1-8b-instant) to parse a raw forwarded email into
    structured client intake data. Falls back to a minimal stub if no key."""
    raw = body.raw_email.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="raw_email is required")

    if GROQ_API_KEY:
        def _do_groq():
            import httpx
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": EMAIL_PARSE_PROMPT + raw}],
                    "temperature": 0.1,
                    "max_tokens": 600,
                },
                timeout=20,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # strip accidental markdown fences
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        try:
            parsed = ai_client.call_ai("groq", "parse-email", _do_groq, db_session_factory=SessionLocal)
            return {"ok": True, "source": "groq", "data": parsed}
        except (AIUnavailable, Exception) as e:
            logger.warning("ai.parse-email groq failed", extra={"error": str(e)[:200]})
            # fall through to Gemini

    if GEMINI_API_KEY:
        def _do_gemini():
            import httpx
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": EMAIL_PARSE_PROMPT + raw}]}]},
                timeout=20,
            )
            resp.raise_for_status()
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        try:
            parsed = ai_client.call_ai("gemini", "parse-email", _do_gemini, db_session_factory=SessionLocal)
            return {"ok": True, "source": "gemini", "data": parsed}
        except (AIUnavailable, Exception) as e:
            logger.warning("ai.parse-email gemini failed", extra={"error": str(e)[:200]})

    # No AI key configured — return empty stub so UI still works
    return {"ok": True, "source": "none", "data": {
        "first_name": None, "last_name": None, "email": None, "phone": None,
        "home_airport": None, "travel_goals": None, "trips": [], "points": [],
        "cabin_pref": None, "notes": raw[:300],
    }}


# ── Intake ──
# The form posts a flat dict with a fixed core plus dynamic trip{N}_* / pts_*
# keys, so validation happens on the parsed dict: required well-formed email,
# every value length-capped, total payload bounded.
INTAKE_MAX_FIELD_LEN = 5000
INTAKE_MAX_KEYS = 120
_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_intake(data: dict) -> dict:
    if not isinstance(data, dict) or len(data) > INTAKE_MAX_KEYS:
        raise HTTPException(status_code=422, detail="Invalid submission")
    email = str(data.get("email", "")).strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254 or "\n" in email or "\r" in email:
        raise HTTPException(status_code=422, detail="A valid email address is required")
    clean = {}
    for k, v in data.items():
        key = str(k)[:60]
        val = str(v) if v is not None else ""
        if len(val) > INTAKE_MAX_FIELD_LEN:
            raise HTTPException(status_code=422, detail=f"Field '{key}' is too long")
        clean[key] = val
    clean["email"] = email
    return clean


@app.post("/api/intake")
@limiter.limit("10/hour")
async def submit_intake(request: Request, db: Session = Depends(get_db)):
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON")
    data = validate_intake(raw)
    # Honeypot: the form has an invisible 'hp' field — humans never fill it,
    # bots do. Accept silently (so bots don't adapt) but store nothing.
    if str(data.get("hp", "")).strip():
        logger.warning("intake honeypot tripped — submission discarded")
        return {"ok": True, "id": 0}
    data.pop("hp", None)
    # Funnel: record a submit event if the form sent a session id (stripped from stored payload)
    session_id = str(data.pop("_session_id", "") or "")[:64]
    consent_at = dt.datetime.utcnow() if str(data.get("consent", "")).lower() in ("true", "1", "yes", "on") else None
    rec = Intake(
        first_name=data.get("first_name", "")[:100],
        last_name=data.get("last_name", "")[:100],
        email=data.get("email", ""),
        phone=data.get("phone", "")[:40],
        payload=json.dumps(data),
        consent_at=consent_at,
    )
    db.add(rec)
    if session_id:
        db.add(FunnelEvent(
            session_id=session_id,
            event="submit",
            page="intake",
            utm_source=str(data.get("utm_source", ""))[:100],
            utm_medium=str(data.get("utm_medium", ""))[:100],
            utm_campaign=str(data.get("utm_campaign", ""))[:100],
        ))
    db.commit()
    name = f"{data.get('first_name','')} {data.get('last_name','')}".strip() or "Someone"
    # Notify admin
    send_email(
        subject=f"New DAT Intake: {name}",
        body=format_intake_email(data),
        reply_to=data.get("email", ""),
    )
    # Confirmation email to client
    client_email = data.get("email", "")
    if client_email:
        confirmation_body = f"""Hi {data.get('first_name', 'there')},

Thanks for reaching out to District Award Travel! We've received your profile and will be in touch shortly to discuss how we can help you make the most of your points and miles.

Here's a quick recap of what you submitted:
  Home Airport: {data.get('home_airport', '—')}
  Cabin Preference: {data.get('cabin_pref', '—')}
  Travel Goals: {data.get('travel_goals', '—')}

We typically respond within 1-2 business days. In the meantime, feel free to reply to this email with any questions.

— The District Award Travel Team
districtawardtravel@gmail.com
"""
        send_email_to(
            to=client_email,
            subject="We received your submission — District Award Travel",
            body=confirmation_body,
        )
    return {"ok": True, "id": rec.id}


# ── Public trust surface: funnel tracking, proof stats, savings examples ──
EARNED_PROOF_STATUSES = ("booked", "invoiced", "paid")


@app.post("/api/track")
@limiter.limit("120/hour")
async def track_event(request: Request, body: TrackIn, db: Session = Depends(get_db)):
    """First-party funnel beacon. Must never break page UX beyond validation."""
    try:
        db.add(FunnelEvent(
            session_id=body.session_id,
            event=body.event,
            page=body.page,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
        ))
        db.commit()
    except Exception as e:
        logger.warning("funnel.track write failed", extra={"error": str(e)[:200]})
    return {"ok": True}


def _earned_records(db: Session):
    return db.query(SavingsRecord).filter(SavingsRecord.status.in_(EARNED_PROOF_STATUSES)).all()


@app.get("/api/public/proof")
@limiter.limit("60/minute")
def public_proof(request: Request, db: Session = Depends(get_db)):
    """Aggregate stats only — never any client data, names, or emails."""
    recs = _earned_records(db)
    total = sum(
        calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        for r in recs
    )
    trips = len(recs)
    cpp_recs = [r for r in recs if r.points_used and r.points_used > 0]
    avg_cpp_tenths = None
    if len(cpp_recs) >= PROOF_MIN_CPP_RECORDS:
        gross_sum = sum(
            calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
            for r in cpp_recs
        )
        pts_sum = sum(r.points_used for r in cpp_recs)
        if pts_sum > 0:
            avg_cpp_tenths = (gross_sum * 1000) // pts_sum
    return {
        "total_savings_cents": total if total >= PROOF_MIN_SAVINGS_CENTS else None,
        "trips_planned": trips if trips >= PROOF_MIN_TRIPS else None,
        "avg_cpp_tenths": avg_cpp_tenths,
    }


@app.get("/api/public/stats")
@limiter.limit("60/minute")
def public_stats(request: Request, db: Session = Depends(get_db)):
    """Public aggregate savings stats — no auth required, no client data exposed."""
    recs = db.query(SavingsRecord).filter(
        SavingsRecord.status.in_(["booked", "invoiced", "paid"])
    ).all()
    total_savings_cents = 0
    for rec in recs:
        gross = calc_gross_savings(
            rec.cash_benchmark_cents,
            rec.award_taxes_fees_cents,
            rec.other_out_of_pocket_cents,
        )
        total_savings_cents += max(gross, 0)
    trips_completed = len(recs)
    avg_savings_cents = (total_savings_cents // trips_completed) if trips_completed else 0
    return {
        "total_savings_cents": total_savings_cents,
        "trips_completed": trips_completed,
        "avg_savings_cents": avg_savings_cents,
    }


# Illustrative seeded examples — labeled real:false server-side so a fake can
# never render as documented. (route, cash_cents, taxes_fees_cents, other_cents, points_used)
ILLUSTRATIVE_EXAMPLES = [
    ("IAD → Tokyo (HND) · Business",        428000, 11240,    0,  75000),
    ("DCA → Paris (CDG) · Premium Economy", 168000,  9830,    0,  60000),
    ("BWI → Cancún · Economy, family of 4", 152000, 22400,    0, 100000),
    ("Maui · 5-night Hyatt hotel",          297500,     0,    0,  87500),
]


def _example_row(route, cash_cents, taxes_cents, other_cents, points_used, real):
    gross = calc_gross_savings(cash_cents, taxes_cents, other_cents)
    fee = calc_fee(gross, 1000)
    return {
        "route": route,
        "cash_cents": cash_cents,
        "out_of_pocket_cents": taxes_cents + other_cents,
        "points_used": points_used,
        "savings_cents": gross,
        "fee_cents": fee,
        "net_win_cents": gross - fee,
        "real": real,
    }


@app.get("/api/public/examples")
@limiter.limit("60/minute")
def public_examples(request: Request, db: Session = Depends(get_db)):
    """Up to 6 anonymized savings examples. NO names or emails, ever."""
    rows = []
    recs = db.query(SavingsRecord).filter(
        SavingsRecord.status.in_(EARNED_PROOF_STATUSES)
    ).order_by(SavingsRecord.created_at.desc()).all()
    for r in recs:
        gross = calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        if not r.trip_label or not r.trip_label.strip() or not r.points_used or r.points_used <= 0 or gross <= 0:
            continue
        row = _example_row(
            r.trip_label, r.cash_benchmark_cents,
            r.award_taxes_fees_cents, r.other_out_of_pocket_cents,
            r.points_used, True,
        )
        row["fee_cents"] = calc_fee(gross, r.fee_rate_bps)
        row["net_win_cents"] = gross - row["fee_cents"]
        rows.append(row)
        if len(rows) >= 6:
            break
    if len(rows) < 4:
        for ex in ILLUSTRATIVE_EXAMPLES:
            if len(rows) >= 6:
                break
            rows.append(_example_row(*ex, real=False))
    return rows


@app.get("/api/admin/funnel")
def admin_funnel(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """Weekly funnel (last 8 ISO weeks): page_view / form_start / submit counts
    plus a by-utm_source breakdown of submits."""
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=56)
    events = db.query(FunnelEvent).filter(FunnelEvent.created_at >= cutoff).all()
    weeks: dict = {}
    for e in events:
        iso = e.created_at.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        w = weeks.setdefault(key, {
            "week": key, "page_view": 0, "form_start": 0, "submit": 0,
            "submits_by_utm_source": {},
        })
        if e.event in ("page_view", "form_start", "submit"):
            w[e.event] += 1
        if e.event == "submit":
            src = e.utm_source or "(direct)"
            w["submits_by_utm_source"][src] = w["submits_by_utm_source"].get(src, 0) + 1
    return {"weeks": sorted(weeks.values(), key=lambda w: w["week"])}


# ── Auth ──
@app.post("/api/admin/login")
@limiter.limit("5/15minutes")
def admin_login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == body.email.lower()).first()
    if not admin or not verify_pw(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(admin.email, "admin"), "name": admin.name, "role": "admin"}


@app.post("/api/auth/login")
@limiter.limit("5/15minutes")
def client_login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.email == body.email.lower()).first()
    if not client or not verify_pw(body.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(client.email, "client"), "name": client.name, "role": "client"}


# ── Client self ──
# In-process change counters drive the SSE stream: admin mutations bump the
# client's version; the stream watches the dict (zero DB connections held per
# stream — Postgres impact of N portal tabs is nil between events). Single
# Render instance → in-process state is authoritative. Restart = clients
# reconnect and refetch, which is the correct behavior anyway.
_client_versions: dict = {}


def bump_client_version(email: str):
    if email:
        _client_versions[email] = _client_versions.get(email, 0) + 1


@app.get("/api/client/stream")
async def client_stream(token: str = ""):
    """SSE: emits 'changed' when the client's data is mutated, comment
    heartbeats every 30s, and ends after 5 minutes (client auto-reconnects)
    so Render spin-downs and dead connections can't accumulate.

    EventSource can't set headers, so auth is the JWT in a query param. The
    request-logging middleware logs only the path, never the query string.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    email = payload["sub"]

    async def gen():
        import asyncio
        last_version = _client_versions.get(email, 0)
        started = _time.monotonic()
        last_beat = started
        yield f"event: hello\ndata: {{\"v\": {last_version}}}\n\n"
        while _time.monotonic() - started < 300:  # 5 min, then reconnect
            await asyncio.sleep(2)
            v = _client_versions.get(email, 0)
            now = _time.monotonic()
            if v != last_version:
                last_version = v
                yield f"event: changed\ndata: {{\"v\": {v}}}\n\n"
            elif now - last_beat >= 30:
                last_beat = now
                yield ": heartbeat\n\n"
        yield "event: bye\ndata: {}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/client/me")
def client_me(identity: dict = Depends(current_identity), db: Session = Depends(get_db)):
    if identity.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.query(Client).filter(Client.email == identity["sub"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = json.loads(client.data or "{}")
    payload.update({"name": client.name, "tier": client.tier, "email": client.email})
    # compute lifetime savings for this client (booked, invoiced, paid — not void/draft/presented)
    EARNED_STATUSES = {"booked", "invoiced", "paid"}
    savings_recs = db.query(SavingsRecord).filter(
        SavingsRecord.client_id == client.id,
        SavingsRecord.status.in_(list(EARNED_STATUSES))
    ).all()
    lifetime_savings_cents = sum(
        calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        for r in savings_recs
    )
    payload["lifetime_savings_cents"] = lifetime_savings_cents

    # Real trip pipeline rows (from trip_requests table) so the portal can show
    # live workflow status, not just the legacy data.trips JSON.
    trips = db.query(TripRequest).filter(TripRequest.client_id == client.id).order_by(TripRequest.created_at.desc()).all()
    payload["pipeline_trips"] = [
        {
            "id": t.id,
            "destination": t.destination,
            "origin": t.origin,
            "dates": t.dates,
            "passengers": t.passengers,
            "cabin": t.cabin,
            "workflow_status": t.workflow_status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in trips
    ]

    # Per-trip savings breakdown the client is allowed to see (no internal notes,
    # no screenshots of our research — just their documented wins and the fee).
    all_recs = db.query(SavingsRecord).filter(
        SavingsRecord.client_id == client.id,
        SavingsRecord.status.in_(["booked", "invoiced", "paid"])
    ).order_by(SavingsRecord.created_at.desc()).all()
    savings_breakdown = []
    total_fee_cents = 0
    for r in all_recs:
        gross = calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        fee = calc_fee(gross, r.fee_rate_bps)
        total_fee_cents += fee
        savings_breakdown.append({
            "trip_label": r.trip_label,
            "cash_benchmark_cents": r.cash_benchmark_cents,
            "points_used": r.points_used,
            "points_program": r.points_program,
            "gross_savings_cents": gross,
            "fee_cents": fee,
            "status": r.status,
            "invoice_number": r.invoice_number,
            "report_url": f"/api/report/{r.report_token}" if r.report_token else None,
        })
    payload["savings_breakdown"] = savings_breakdown
    payload["total_fee_cents"] = total_fee_cents
    payload["trips_count"] = len(trips)
    return payload


class UpdateClientDataIn(BaseModel):
    data: dict


@app.put("/api/client/me")
def update_client_me(body: UpdateClientDataIn, identity: dict = Depends(current_identity), db: Session = Depends(get_db)):
    """Client updates their own profile data (preferences, trips, etc.)."""
    if identity.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.query(Client).filter(Client.email == identity["sub"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    existing = json.loads(client.data or "{}")
    # Deep merge: if body.data["preferences"] exists, merge it; same for other top-level keys
    for key, val in body.data.items():
        if key in ["preferences", "trips", "points", "savings", "messages", "recommendations"]:
            if isinstance(val, dict) and isinstance(existing.get(key), dict):
                existing[key].update(val)
            else:
                existing[key] = val
        else:
            existing[key] = val
    client.data = json.dumps(existing)
    db.commit()
    return {"ok": True}


# ── Admin: client management ──
@app.get("/api/admin/clients")
def list_clients(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return [
        {"email": c.email, "name": c.name, "tier": c.tier, "created_at": c.created_at.isoformat()}
        for c in clients
    ]


@app.get("/api/admin/clients/{email}")
def get_client(email: str, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Return full client data including their portal JSON for the admin profile drawer."""
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = json.loads(client.data or "{}")
    payload.update({"name": client.name, "tier": client.tier, "email": client.email,
                     "created_at": client.created_at.isoformat()})
    return payload


@app.post("/api/admin/clients")
def create_client(body: ClientIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(Client).filter(Client.email == email).first():
        raise HTTPException(status_code=409, detail="A client with that email already exists")
    client = Client(
        email=email,
        password_hash=hash_pw(body.password),
        name=body.name,
        tier=body.tier,
        data=json.dumps(body.data or {}),
    )
    db.add(client)
    db.commit()
    return {"ok": True, "email": email}


@app.put("/api/admin/clients/{email}")
def update_client_data(email: str, body: UpdateClientDataIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Merge a partial data dict into an existing client's JSON payload."""
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    existing = json.loads(client.data or "{}")
    existing.update(body.data)
    client.data = json.dumps(existing)
    db.commit()
    bump_client_version(client.email)
    return {"ok": True}


class PointEntryIn(BaseModel):
    program: str
    balance: str
    expiration_date: Optional[str] = None
    tier: Optional[str] = None


@app.post("/api/admin/clients/{email}/points")
def add_client_point(email: str, body: PointEntryIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Add or update a single points-program entry in a client's profile."""
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = json.loads(client.data or "{}")
    points = data.get("points", [])
    existing_pt = next((p for p in points if p.get("program", "").lower() == body.program.lower()), None)
    entry = {
        "program": body.program,
        "balance": body.balance,
        "expiration_date": body.expiration_date,
        "tier": body.tier,
    }
    if existing_pt:
        existing_pt.update(entry)
    else:
        points.append(entry)
    data["points"] = points
    client.data = json.dumps(data)
    db.commit()
    bump_client_version(client.email)
    return {"ok": True}


@app.delete("/api/admin/clients/{email}")
def delete_client(email: str, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Permanently delete a client record. Use only for test/duplicate accounts.

    Refuses while savings records or trip requests reference the client —
    deleting would orphan revenue/audit history. Void or reassign those first.
    """
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    savings_count = db.query(SavingsRecord).filter(SavingsRecord.client_id == client.id).count()
    trips_count = db.query(TripRequest).filter(TripRequest.client_id == client.id).count()
    if savings_count or trips_count:
        raise HTTPException(
            status_code=409,
            detail=f"Client has {savings_count} savings record(s) and {trips_count} trip(s). "
                   "Delete/void those first — deleting the client would orphan ledger history.",
        )
    db.delete(client)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/expiring-points")
def expiring_points(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """All client point balances with an expiration_date, sorted soonest first.
    Returns rows within 180 days; includes urgency level for the admin UI."""
    clients = db.query(Client).all()
    today = dt.date.today()
    rows = []
    for c in clients:
        data = json.loads(c.data or "{}")
        for p in data.get("points", []):
            exp_str = p.get("expiration_date") or ""
            if not exp_str:
                continue
            try:
                exp_date = dt.date.fromisoformat(str(exp_str)[:10])
            except ValueError:
                continue
            days_left = (exp_date - today).days
            if days_left > 180 or days_left < 0:
                continue
            rows.append({
                "client_name": c.name,
                "client_email": c.email,
                "program": p.get("program") or p.get("name") or "Unknown",
                "balance": p.get("balance") or p.get("points") or 0,
                "expiration_date": str(exp_date),
                "days_left": days_left,
                "urgency": "urgent" if days_left <= 30 else "warning" if days_left <= 90 else "calm",
            })
    rows.sort(key=lambda r: r["days_left"])
    return rows


class SendMessageIn(BaseModel):
    client_email: str
    subject: str
    body: str
    is_plan: bool = False
    plan_details: Optional[dict] = None


@app.post("/api/admin/send-message")
def send_message(msg_in: SendMessageIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Save a message to a client's portal and optionally send email notification."""
    client = db.query(Client).filter(Client.email == msg_in.client_email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    data = json.loads(client.data or "{}")
    messages = data.get("messages", [])

    message = {
        "from": "Braden — DAT",
        "sender": "advisor",
        "time": dt.datetime.utcnow().isoformat(),
        "subject": msg_in.subject,
        "text": msg_in.body,
        "unread": True,
    }
    if msg_in.is_plan and msg_in.plan_details:
        message["plan"] = msg_in.plan_details

    messages.append(message)
    data["messages"] = messages
    client.data = json.dumps(data)
    db.commit()
    bump_client_version(client.email)

    # Also send email notification (chat replies have no subject)
    email_subject = f"New message: {msg_in.subject}" if msg_in.subject.strip() else "New message from Braden — District Award Travel"
    send_email_to(
        client.email,
        email_subject,
        f"Hi {client.name.split()[0]},\n\n{msg_in.body}\n\nLog in to your portal to view this message.\n\nBest,\nBraden\nDistrict Award Travel"
    )

    return {"ok": True, "message_id": len(messages) - 1}


# ── Two-way chat: client ↔ advisor ──
# Messages live in the client's data.messages JSON array (same thread the
# admin already writes to). sender: "advisor" | "client". unread = unread by
# client; unread_admin = unread by advisor.

class ClientMessageIn(BaseModel):
    body: str


@app.post("/api/client/message")
@limiter.limit("30/minute")
def client_send_message(request: Request, msg_in: ClientMessageIn,
                        identity: dict = Depends(current_identity), db: Session = Depends(get_db)):
    """Client sends a chat message to the advisor."""
    if identity.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.query(Client).filter(Client.email == identity["sub"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    text = (msg_in.body or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message is empty")
    if len(text) > 5000:
        raise HTTPException(status_code=422, detail="Message too long (5000 chars max)")

    data = json.loads(client.data or "{}")
    messages = data.get("messages", [])
    messages.append({
        "from": client.name,
        "sender": "client",
        "time": dt.datetime.utcnow().isoformat(),
        "text": text,
        "unread_admin": True,
    })
    data["messages"] = messages
    client.data = json.dumps(data)
    db.commit()
    bump_client_version(client.email)  # update the client's other open tabs

    # Notify the advisor by email so nothing sits unanswered
    send_email(
        f"💬 New portal message from {client.name}",
        f"{client.name} ({client.email}) wrote:\n\n{text}\n\nReply from the admin dashboard → Messages.",
        reply_to=client.email,
    )
    return {"ok": True, "message_id": len(messages) - 1}


@app.post("/api/client/messages/read")
def client_mark_messages_read(identity: dict = Depends(current_identity), db: Session = Depends(get_db)):
    """Client opened the thread — clear unread flags on advisor messages."""
    if identity.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.query(Client).filter(Client.email == identity["sub"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = json.loads(client.data or "{}")
    changed = False
    for m in data.get("messages", []):
        if m.get("unread") and m.get("sender") != "client":
            m["unread"] = False
            changed = True
    if changed:
        client.data = json.dumps(data)
        db.commit()
    return {"ok": True}


@app.get("/api/admin/inbox")
def admin_inbox(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Chat inbox: every client with their last message + unread-by-admin count,
    sorted by most recent activity. Powers the WhatsApp-style Messages panel."""
    rows = []
    for c in db.query(Client).all():
        data = json.loads(c.data or "{}")
        msgs = data.get("messages", [])
        last = msgs[-1] if msgs else None
        rows.append({
            "email": c.email,
            "name": c.name,
            "tier": c.tier,
            "unread": sum(1 for m in msgs if m.get("unread_admin")),
            "last": {
                "sender": last.get("sender", "advisor"),
                "text": (last.get("text") or "")[:140],
                "time": last.get("time", ""),
            } if last else None,
        })
    rows.sort(key=lambda r: (r["last"]["time"] if r["last"] else ""), reverse=True)
    return rows


@app.post("/api/admin/clients/{email}/messages/read")
def admin_mark_messages_read(email: str, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Advisor opened a thread — clear unread_admin flags on client messages."""
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = json.loads(client.data or "{}")
    changed = False
    for m in data.get("messages", []):
        if m.get("unread_admin"):
            m["unread_admin"] = False
            changed = True
    if changed:
        client.data = json.dumps(data)
        db.commit()
    return {"ok": True}


# ── AI: Gemini Vision document scanner ──
SCAN_PROMPT = """You are analyzing a loyalty program document image. This could be an airline app screenshot, hotel rewards page, credit card statement, or any points/miles program.

Extract the following and return ONLY valid JSON — no markdown, no extra text:
{
  "program": "full program name (e.g. United MileagePlus, Marriott Bonvoy, Chase Ultimate Rewards)",
  "balance": "points or miles balance as shown (e.g. 45,230)",
  "expiration_date": "expiration date in YYYY-MM-DD format if visible, null otherwise",
  "tier": "elite status tier if visible (e.g. Gold, Platinum, 1K), null otherwise",
  "card_type": "credit card name if this is a card statement, null otherwise",
  "notes": "any other relevant details (upcoming expiry warnings, transfer bonuses, etc.) or null"
}
Return ONLY the JSON object, nothing else."""


class ScanDocumentIn(BaseModel):
    image_b64: str
    image_mime: str = "image/jpeg"
    client_email: str = ""


@app.post("/api/ai/scan-document")
async def scan_document(body: ScanDocumentIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Gemini Vision reads a loyalty document image and auto-fills client points data."""
    if not GEMINI_API_KEY:
        return {"ok": False, "error": "AI scanner unavailable — enter balances manually", "manual": True}

    def _do():
        import httpx
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [
                {"text": SCAN_PROMPT},
                {"inline_data": {"mime_type": body.image_mime, "data": body.image_b64}},
            ]}]},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    try:
        extracted = ai_client.call_ai("gemini", "scan-document", _do, db_session_factory=SessionLocal)
    except (AIUnavailable, Exception) as e:
        logger.warning("ai.scan-document failed", extra={"error": str(e)[:200]})
        return {"ok": False, "error": "AI scanner unavailable — enter balances manually", "manual": True}

    saved = False
    if body.client_email:
        client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
        if client:
            data = json.loads(client.data or "{}")
            points = data.get("points", [])
            prog = extracted.get("program", "")
            new_entry = {
                "program": prog,
                "balance": extracted.get("balance", ""),
                "expiration_date": extracted.get("expiration_date"),
                "tier": extracted.get("tier"),
            }
            existing_pt = next((p for p in points if p.get("program", "").lower() == prog.lower()), None)
            if existing_pt:
                existing_pt.update(new_entry)
            else:
                points.append(new_entry)
            data["points"] = points
            client.data = json.dumps(data)
            db.commit()
            saved = True

    return {"ok": True, "source": "gemini", "extracted": extracted, "saved": saved}


# ── AI: Gemini Sweet Spot Oracle ──
SWEET_SPOT_PROMPT = """You are Braden's AI co-pilot at District Award Travel, a points-and-miles advisory firm.

Client points portfolio:
{points_portfolio}

Travel goals: {travel_goals}
Home airport: {home_airport}
Client name: {client_name}

Generate exactly 3 personalized award travel recommendations. Focus on high-value redemptions (ideally 2+ cpp) achievable with their current balances.

Key sweet spots to consider:
- Chase UR → Hyatt (hotels, 2-5 cpp)
- Amex MR → ANA Business/First Class (4-5 cpp)
- Citi TYP → Turkish Miles&Smiles (Star Alliance, great rates)
- United MileagePlus → Lufthansa/ANA partner awards
- Alaska Mileage Plan → Cathay Pacific, Finnair, JAL
- Flying Blue Promo Awards (monthly 30-50% off sales)
- Delta SkyMiles → partner redemptions during sales
- Marriott/Hilton points → category awards or transfer to airlines
- Capital One → Turkish/Avianca (1:1 transfers)

Return ONLY valid JSON array — no markdown, no extra text:
[
  {
    "origin": "3-letter IATA code",
    "destination": "3-letter IATA code",
    "destination_city": "City name",
    "program": "loyalty program name for booking",
    "cabin": "Economy|Business|First",
    "points_needed": integer,
    "est_cash_value": integer (USD, one-way or per night),
    "cpp": float,
    "why": "1-2 sentences personalised to this client's goals and points",
    "book_link": "direct URL to award search page for this program",
    "urgency": "low|medium|high"
  }
]"""


class SweetSpotIn(BaseModel):
    client_email: str


@app.post("/api/ai/sweet-spots")
async def sweet_spots(body: SweetSpotIn, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Gemini generates 3 personalized award recommendations + seats.aero live availability."""
    client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not GEMINI_API_KEY:
        return {"ok": False, "error": "AI recommendations unavailable — no AI key configured", "manual": True}

    data = json.loads(client.data or "{}")
    points = data.get("points", [])
    travel_goals = data.get("travel_goals", "not specified")
    home_airport = data.get("home_airport", "not specified")

    pts_str = "\n".join([
        f"- {p.get('program','')}: {p.get('balance','?')} pts"
        + (f" (expires {p['expiration_date']})" if p.get("expiration_date") else "")
        for p in points
    ]) or "No points data on file yet — generate general top-value recommendations."

    prompt = (SWEET_SPOT_PROMPT
              .replace("{points_portfolio}", pts_str)
              .replace("{travel_goals}", travel_goals)
              .replace("{home_airport}", home_airport)
              .replace("{client_name}", client.name))

    def _do():
        import httpx
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    try:
        recs = ai_client.call_ai("gemini", "sweet-spots", _do, db_session_factory=SessionLocal)
    except (AIUnavailable, Exception) as e:
        logger.warning("ai.sweet-spots failed", extra={"error": str(e)[:200]})
        return {"ok": False, "error": "AI recommendations unavailable — try again shortly", "manual": True}

    # Enrich with seats.aero live award availability
    if SEATS_AERO_API_KEY:
        import httpx
        prog_map = {
            "united": "united", "delta": "delta", "american": "american",
            "alaska": "alaska", "aeroplan": "aeroplan", "air canada": "aeroplan",
            "lifemiles": "lifemiles", "avianca": "lifemiles",
            "flyingblue": "flyingblue", "flying blue": "flyingblue",
            "british airways": "ba", "virgin atlantic": "virgin_atlantic",
            "turkish": "turkish", "ana": "ana",
        }
        cabin_map = {"Economy": "economy", "Business": "business", "First": "first"}
        start = (dt.date.today() + dt.timedelta(days=30)).strftime("%Y-%m-%d")
        end = (dt.date.today() + dt.timedelta(days=120)).strftime("%Y-%m-%d")

        for rec in recs:
            prog_lower = rec.get("program", "").lower()
            source = next((v for k, v in prog_map.items() if k in prog_lower), None)
            cabin = cabin_map.get(rec.get("cabin", ""), "business")
            if source:
                try:
                    sa = httpx.get(
                        "https://seats.aero/partnerapi/availability",
                        params={
                            "source": source,
                            "origin_airport": rec.get("origin", ""),
                            "destination_airport": rec.get("destination", ""),
                            "cabin": cabin,
                            "start_date": start,
                            "end_date": end,
                        },
                        headers={"Partner-Authorization": SEATS_AERO_API_KEY},
                        timeout=10,
                    )
                    if sa.status_code == 200:
                        avail = sa.json().get("data", [])
                        rec["seats_available"] = len(avail)
                        if avail:
                            rec["next_available_date"] = avail[0].get("Date", "")
                except Exception as e2:
                    logger.warning("seats.aero lookup failed", extra={"destination": rec.get("destination", ""), "error": str(e2)[:200]})

    # Save to client profile
    data["recommendations"] = recs
    data["recommendations_generated_at"] = dt.datetime.utcnow().isoformat()
    client.data = json.dumps(data)
    db.commit()

    return {"ok": True, "recommendations": recs, "client_name": client.name}


# ── AI: Groq multi-thread email importer ──
THREAD_PARSE_PROMPT = """You are an assistant for District Award Travel, a points-and-miles advisory firm.

The advisor has pasted a multi-message email conversation thread with a client or prospect.
Extract all available information and return ONLY valid JSON — no markdown, no extra text.

Schema:
{
  "first_name": string|null,
  "last_name": string|null,
  "email": string|null,
  "phone": string|null,
  "home_airport": string|null,
  "travel_goals": string|null,
  "trips": [{"destination": string, "dates": string}],
  "points": [{"program": string, "balance": string}],
  "cabin_pref": string|null,
  "notes": string|null,
  "conversation_summary": "2-3 sentence summary: what was discussed, any commitments made",
  "action_items": [
    {
      "title": "specific action for the advisor",
      "priority": "critical|high|medium|low",
      "due_days": integer or null
    }
  ]
}

Rules:
- Extract names/emails/phones exactly as written
- Capture ALL mentioned loyalty programs with balances
- action_items = any follow-ups promised, research to do, info to send
- Return ONLY the JSON object.

Thread:
"""


class ParseThreadsIn(BaseModel):
    raw_threads: str


@app.post("/api/ai/parse-threads")
async def parse_threads(body: ParseThreadsIn, _: dict = Depends(require_admin)):
    """Groq parses a multi-message email thread into a client profile + action items."""
    raw = body.raw_threads.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="raw_threads is required")

    def strip_fences(s: str) -> str:
        if s.startswith("```"):
            s = s.split("```")[1]
            if s.startswith("json"):
                s = s[4:]
        return s.strip()

    if GROQ_API_KEY:
        def _do_groq():
            import httpx
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": THREAD_PARSE_PROMPT + raw}],
                    "temperature": 0.1,
                    "max_tokens": 900,
                },
                timeout=25,
            )
            resp.raise_for_status()
            content = strip_fences(resp.json()["choices"][0]["message"]["content"].strip())
            return json.loads(content)
        try:
            parsed = ai_client.call_ai("groq", "parse-threads", _do_groq, db_session_factory=SessionLocal)
            return {"ok": True, "source": "groq", "data": parsed}
        except (AIUnavailable, Exception) as e:
            print(f"[groq] thread parse failed: {e}")

    if GEMINI_API_KEY:
        def _do_gemini():
            import httpx
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": THREAD_PARSE_PROMPT + raw}]}]},
                timeout=25,
            )
            resp.raise_for_status()
            content = strip_fences(resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
            return json.loads(content)
        try:
            parsed = ai_client.call_ai("gemini", "parse-threads", _do_gemini, db_session_factory=SessionLocal)
            return {"ok": True, "source": "gemini", "data": parsed}
        except (AIUnavailable, Exception) as e:
            logger.warning("ai.parse-threads gemini failed", extra={"error": str(e)[:200]})

    return {"ok": True, "source": "none", "data": {
        "first_name": None, "last_name": None, "email": None, "phone": None,
        "home_airport": None, "travel_goals": None, "trips": [], "points": [],
        "cabin_pref": None, "notes": raw[:300],
        "conversation_summary": "AI not available — review manually.",
        "action_items": [],
    }}


# ──────────────────────────────────────────────────────────────────────────
# Savings Ledger endpoints
# ──────────────────────────────────────────────────────────────────────────

@app.post("/api/admin/savings")
def create_savings(body: SavingsCreateIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
    if not client:
        raise HTTPException(404, "Client not found")
    if len(body.benchmark_screenshot) > 2_000_000:  # ~1.5MB base64
        raise HTTPException(422, "Screenshot too large (max ~1.5 MB)")
    captured_at = None
    if body.benchmark_captured_at:
        try:
            captured_at = dt.datetime.fromisoformat(body.benchmark_captured_at)
        except ValueError:
            raise HTTPException(422, "benchmark_captured_at must be ISO datetime")
    rec = SavingsRecord(
        client_id=client.id,
        trip_label=body.trip_label,
        cash_benchmark_cents=body.cash_benchmark_cents,
        benchmark_source=body.benchmark_source,
        benchmark_captured_at=captured_at or dt.datetime.utcnow(),
        benchmark_assumptions=body.benchmark_assumptions,
        benchmark_screenshot=body.benchmark_screenshot,
        option_booked=body.option_booked,
        points_used=body.points_used,
        points_program=body.points_program,
        award_taxes_fees_cents=body.award_taxes_fees_cents,
        other_out_of_pocket_cents=body.other_out_of_pocket_cents,
        fee_rate_bps=body.fee_rate_bps,
        report_token=secrets.token_urlsafe(32),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _savings_row(rec)


@app.get("/api/admin/savings/summary")
def savings_summary(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    recs = db.query(SavingsRecord).filter(SavingsRecord.status != "void").all()
    totals = {"draft": 0, "presented": 0, "booked": 0, "invoiced": 0, "paid": 0}
    fees   = {"draft": 0, "presented": 0, "booked": 0, "invoiced": 0, "paid": 0}
    for r in recs:
        gross = calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        fee   = calc_fee(gross, r.fee_rate_bps)
        if r.status in totals:
            totals[r.status] += gross
            fees[r.status]   += fee
    return {
        "gross_savings_by_status": totals,
        "fees_by_status": fees,
        "owed_cents":      fees["booked"],
        "invoiced_cents":  fees["invoiced"],
        "collected_cents": fees["paid"],
    }


@app.get("/api/admin/savings")
def list_savings(client_email: Optional[str] = None, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    q = db.query(SavingsRecord)
    if client_email:
        client = db.query(Client).filter(Client.email == client_email.lower()).first()
        if not client:
            return []
        q = q.filter(SavingsRecord.client_id == client.id)
    recs = q.order_by(SavingsRecord.created_at.desc()).all()
    return [_savings_row(r) for r in recs]


@app.patch("/api/admin/savings/{record_id}")
def update_savings(record_id: int, body: SavingsPatchIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rec = db.query(SavingsRecord).filter(SavingsRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "Record not found")
    VALID_STATUSES = {"draft", "booked", "invoiced", "paid", "void", "presented"}
    for field, val in body.model_dump(exclude_unset=True).items():
        if field == "status":
            if val not in VALID_STATUSES:
                raise HTTPException(422, f"Invalid status '{val}'")
            rec.status = val
            continue
        if rec.status in ("invoiced", "paid"):
            raise HTTPException(400, "Cannot edit a record in invoiced or paid status")
        if field == "benchmark_screenshot" and val and len(val) > 2_000_000:
            raise HTTPException(422, "Screenshot too large (max ~1.5 MB)")
        if field == "benchmark_captured_at":
            if val:
                try:
                    val = dt.datetime.fromisoformat(val)
                except ValueError:
                    raise HTTPException(422, "benchmark_captured_at must be ISO datetime")
            setattr(rec, "benchmark_captured_at", val)
            continue
        setattr(rec, field, val)
    rec.updated_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return _savings_row(rec)


@app.patch("/api/admin/savings/{record_id}/status")
def advance_status(record_id: int, body: StatusAdvanceIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rec = db.query(SavingsRecord).filter(SavingsRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "Record not found")
    if not is_valid_transition(rec.status, body.new_status):
        raise HTTPException(400, f"Cannot transition from '{rec.status}' to '{body.new_status}'")
    if body.new_status == "invoiced" and not rec.invoice_number:
        year = dt.datetime.utcnow().year
        existing = db.query(SavingsRecord).filter(
            SavingsRecord.invoice_number.like(f"DAT-{year}-%")
        ).all()
        nums = []
        for r in existing:
            try:
                nums.append(int(r.invoice_number.split("-")[-1]))
            except (ValueError, IndexError):
                pass
        next_num = max(nums, default=0) + 1
        rec.invoice_number = f"DAT-{year}-{next_num:04d}"
        rec.invoiced_at = dt.datetime.utcnow()
    if body.new_status == "paid":
        rec.paid_at = dt.datetime.utcnow()
        if body.payment_method:
            rec.payment_method = body.payment_method
    rec.status = body.new_status
    rec.updated_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    row = _savings_row(rec)
    client = db.query(Client).filter(Client.id == rec.client_id).first()
    if client:
        row["client_email"] = client.email
        # status changes move the lifetime-savings counter — wake the stream
        bump_client_version(client.email)
    return row


@app.get("/api/admin/savings/{record_id}/report")
def savings_report_url(record_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rec = db.query(SavingsRecord).filter(SavingsRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "Record not found")
    if not rec.report_token:
        rec.report_token = secrets.token_urlsafe(32)
        db.commit()
    return {"report_url": f"/api/report/{rec.report_token}", "token": rec.report_token}


@app.delete("/api/admin/savings/{record_id}")
def delete_savings(record_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rec = db.query(SavingsRecord).filter(SavingsRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "Record not found")
    if rec.status in ("invoiced", "paid"):
        raise HTTPException(400, "Cannot delete an invoiced or paid record; void it instead")
    db.delete(rec)
    db.commit()
    return {"ok": True}


@app.post("/api/admin/savings/import-legacy")
def import_legacy_savings(body: LegacyImportIn, db: Session = Depends(get_db), admin: dict = Depends(require_admin)):
    """Import savings entries from the old admin localStorage (dat_savings key).

    Idempotent: entries whose trip_label + cash_benchmark_cents (within ±100 cents)
    already exist in the DB are skipped rather than duplicated.
    """
    # Resolve which client record to attach these records to
    lookup_email = (body.client_email or admin.get("sub", "")).lower()
    if not lookup_email:
        raise HTTPException(422, "client_email is required (no admin email in token)")
    client = db.query(Client).filter(Client.email == lookup_email).first()
    if not client:
        raise HTTPException(404, f"Client not found: {lookup_email}")

    imported = 0
    skipped = 0

    for entry in body.entries:
        # ── Extract destination ──────────────────────────────────────────────
        dest = entry.get("dest") or entry.get("destination") or ""
        dest = dest.strip() if dest else ""

        # ── Extract benchmark ────────────────────────────────────────────────
        raw_benchmark = entry.get("benchmark") if entry.get("benchmark") is not None else entry.get("cash_benchmark_cents")
        if raw_benchmark is None:
            skipped += 1
            continue
        try:
            raw_benchmark = int(raw_benchmark)
        except (TypeError, ValueError):
            skipped += 1
            continue

        if not dest or raw_benchmark <= 0:
            skipped += 1
            continue

        # Convert dollars → cents if value looks like dollars (< 100 000 and > 0)
        if 0 < raw_benchmark < 100000:
            benchmark_cents = raw_benchmark * 100
        else:
            benchmark_cents = raw_benchmark

        # ── Extract taxes ────────────────────────────────────────────────────
        raw_taxes = entry.get("taxes") if entry.get("taxes") is not None else entry.get("award_taxes_fees_cents", 0)
        try:
            raw_taxes = int(raw_taxes)
        except (TypeError, ValueError):
            raw_taxes = 0
        # Convert dollars → cents if value looks like dollars (< 100 000)
        if 0 < raw_taxes < 100000:
            taxes_cents = raw_taxes * 100
        else:
            taxes_cents = raw_taxes

        # ── Extract points ───────────────────────────────────────────────────
        raw_pts = entry.get("pts") if entry.get("pts") is not None else entry.get("points_used", 0)
        try:
            points_used = int(raw_pts)
        except (TypeError, ValueError):
            points_used = 0

        # ── Extract date ─────────────────────────────────────────────────────
        raw_date = entry.get("date") or entry.get("created_at") or ""
        created_at = None
        if raw_date:
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                try:
                    created_at = dt.datetime.strptime(str(raw_date)[:26], fmt)
                    break
                except ValueError:
                    pass
            if created_at is None:
                try:
                    created_at = dt.datetime.fromisoformat(str(raw_date)[:26])
                except ValueError:
                    created_at = None

        # ── Idempotency check ────────────────────────────────────────────────
        existing = db.query(SavingsRecord).filter(
            SavingsRecord.client_id == client.id,
            SavingsRecord.trip_label == dest,
        ).all()
        duplicate = any(abs(r.cash_benchmark_cents - benchmark_cents) < 100 for r in existing)
        if duplicate:
            skipped += 1
            continue

        # ── Create record ────────────────────────────────────────────────────
        rec = SavingsRecord(
            client_id=client.id,
            trip_label=dest,
            cash_benchmark_cents=benchmark_cents,
            award_taxes_fees_cents=taxes_cents,
            points_used=points_used,
            fee_rate_bps=1000,
            status="booked",
            report_token=secrets.token_urlsafe(32),
        )
        if created_at is not None:
            rec.created_at = created_at
        db.add(rec)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


@app.get("/api/admin/savings/invoice/{record_id}")
def savings_invoice(record_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """Return a printable HTML invoice for a savings record.

    Auto-assigns invoice_number and invoiced_at if they are empty, then
    commits those values so subsequent calls return the same invoice number.
    """
    from fastapi.responses import HTMLResponse

    rec = db.query(SavingsRecord).filter(SavingsRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "Record not found")

    client = db.query(Client).filter(Client.id == rec.client_id).first()
    client_name = client.name if client else "Client"

    # Auto-assign invoice number if missing
    if not rec.invoice_number:
        year = dt.datetime.utcnow().year
        existing = db.query(SavingsRecord).filter(
            SavingsRecord.invoice_number.like(f"DAT-{year}-%")
        ).all()
        nums = []
        for r in existing:
            try:
                nums.append(int(r.invoice_number.split("-")[-1]))
            except (ValueError, IndexError):
                pass
        next_num = max(nums, default=0) + 1
        rec.invoice_number = f"DAT-{year}-{next_num:04d}"
        rec.invoiced_at = dt.datetime.utcnow()
        db.commit()
        db.refresh(rec)

    gross = calc_gross_savings(rec.cash_benchmark_cents, rec.award_taxes_fees_cents, rec.other_out_of_pocket_cents)
    fee   = calc_fee(gross, rec.fee_rate_bps)

    issue_date = (rec.invoiced_at or dt.datetime.utcnow()).date()
    due_date   = issue_date + dt.timedelta(days=30)

    def fmt_usd(cents: int) -> str:
        sign = "-" if cents < 0 else ""
        cents = abs(cents)
        return f"{sign}${cents // 100:,}.{cents % 100:02d}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Invoice {rec.invoice_number} — {rec.trip_label or "Trip"}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f3f4f6; color: #111827; padding: 32px 16px; }}
  .page {{ background: #fff; max-width: 720px; margin: 0 auto; padding: 48px; border: 1px solid #d1d5db; border-radius: 8px; }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; }}
  .brand {{ font-size: 1.25rem; font-weight: 800; color: #d97706; letter-spacing: .02em; }}
  .brand-sub {{ font-size: .8rem; color: #6b7280; margin-top: 2px; }}
  .invoice-meta {{ text-align: right; }}
  .invoice-num {{ font-size: 1.4rem; font-weight: 700; color: #111827; }}
  .invoice-meta p {{ font-size: .85rem; color: #6b7280; margin-top: 4px; }}
  .divider {{ border: none; border-top: 2px solid #e5e7eb; margin: 24px 0; }}
  .parties {{ display: flex; justify-content: space-between; margin-bottom: 32px; }}
  .party h3 {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; color: #9ca3af; margin-bottom: 6px; }}
  .party p {{ font-size: .9rem; color: #111827; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
  thead th {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; padding: 8px 12px; text-align: left; border-bottom: 2px solid #e5e7eb; }}
  thead th:last-child {{ text-align: right; }}
  tbody td {{ padding: 12px 12px; border-bottom: 1px solid #f3f4f6; font-size: .9rem; color: #374151; vertical-align: top; }}
  tbody td:last-child {{ text-align: right; font-weight: 500; }}
  .total-row td {{ padding: 14px 12px; font-size: 1rem; font-weight: 700; color: #d97706; border-top: 2px solid #e5e7eb; border-bottom: none; }}
  .remittance {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 16px 20px; margin-top: 8px; }}
  .remittance h4 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: #92400e; margin-bottom: 8px; }}
  .remittance p {{ font-size: .9rem; color: #78350f; line-height: 1.6; }}
  .footer {{ margin-top: 32px; font-size: .75rem; color: #9ca3af; text-align: center; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .page {{ border: none; border-radius: 0; padding: 24px; }}
  }}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <div>
      <div class="brand">District Award Travel</div>
      <div class="brand-sub">districtawardtravel@gmail.com</div>
    </div>
    <div class="invoice-meta">
      <div class="invoice-num">INVOICE</div>
      <p>{rec.invoice_number}</p>
      <p>Issued: {issue_date.strftime('%B %d, %Y')}</p>
      <p>Due: {due_date.strftime('%B %d, %Y')}</p>
    </div>
  </div>

  <hr class="divider">

  <div class="parties">
    <div class="party">
      <h3>Bill To</h3>
      <p><strong>{client_name}</strong><br>
      {'<br>' + client.email if client else ''}</p>
    </div>
    <div class="party" style="text-align:right;">
      <h3>From</h3>
      <p><strong>District Award Travel</strong><br>
      districtawardtravel@gmail.com</p>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Description</th>
        <th>Detail</th>
        <th>Amount</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>{rec.trip_label or "Award Travel Booking"}</strong><br>
            <span style="font-size:.8rem;color:#6b7280;">Cash value of award ticket(s)</span></td>
        <td style="font-size:.85rem;color:#6b7280;">Benchmark</td>
        <td>{fmt_usd(rec.cash_benchmark_cents)}</td>
      </tr>
      {'<tr><td>Award Taxes &amp; Fees</td><td style="font-size:.85rem;color:#6b7280;">Out-of-pocket</td><td style="color:#6b7280;">(' + fmt_usd(rec.award_taxes_fees_cents) + ')</td></tr>' if rec.award_taxes_fees_cents else ''}
      <tr>
        <td><strong>Gross Savings</strong></td>
        <td></td>
        <td style="color:#059669;font-weight:700;">{fmt_usd(gross)}</td>
      </tr>
      <tr class="total-row">
        <td>District Advisory Fee (10%)</td>
        <td></td>
        <td>{fmt_usd(fee)}</td>
      </tr>
    </tbody>
  </table>

  <div class="remittance">
    <h4>Payment Instructions</h4>
    <p>
      Please remit <strong>{fmt_usd(fee)}</strong> by {due_date.strftime('%B %d, %Y')}.<br>
      Pay via <strong>Venmo</strong> @bsalsa2 &nbsp;|&nbsp; <strong>Zelle</strong> bradensalcetti@icloud.com<br>
      Reference invoice <strong>{rec.invoice_number}</strong> when paying.
    </p>
  </div>

  <div class="footer">District Award Travel &mdash; Thank you for flying smarter.</div>
</div>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/api/report/{token}")
@limiter.limit("30/minute")
def savings_report(request: Request, token: str, db: Session = Depends(get_db)):
    rec = db.query(SavingsRecord).filter(SavingsRecord.report_token == token).first()
    if not rec:
        raise HTTPException(404, "Report not found")
    client = db.query(Client).filter(Client.id == rec.client_id).first()
    client_name = client.name if client else "Client"
    gross = calc_gross_savings(rec.cash_benchmark_cents, rec.award_taxes_fees_cents, rec.other_out_of_pocket_cents)
    fee   = calc_fee(gross, rec.fee_rate_bps)
    cpp   = calc_cpp_tenths(gross, rec.points_used)

    def fmt_usd(cents: int) -> str:
        sign = "-" if cents < 0 else ""
        cents = abs(cents)
        return f"{sign}${cents // 100:,}.{cents % 100:02d}"

    cpp_display = f"{cpp // 10}.{cpp % 10}¢/pt" if rec.points_used else "N/A"

    screenshot_html = ""
    if rec.benchmark_screenshot:
        screenshot_html = f'<img src="{rec.benchmark_screenshot}" alt="Benchmark screenshot" style="max-width:100%;border:1px solid #e5e7eb;border-radius:6px;margin-top:8px;">'

    date_str = rec.benchmark_captured_at.strftime('%B %d, %Y') if rec.benchmark_captured_at else dt.datetime.utcnow().strftime('%B %d, %Y')
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Savings Report — {rec.trip_label or "Trip"}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#f4f3f1;color:#1c1917;-webkit-font-smoothing:antialiased}}
.page{{max-width:720px;margin:40px auto;padding:0 20px 60px}}
.card{{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10),0 1px 4px rgba(0,0,0,.06)}}
.rpt-head{{background:#0c0905;padding:32px 36px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px}}
.rpt-brand{{color:#fff;font-size:15px;font-weight:900;letter-spacing:-.3px}}
.rpt-brand span{{color:#f97316}}
.rpt-tagline{{color:rgba(255,255,255,.45);font-size:12px;margin-top:3px}}
.rpt-badge{{background:rgba(249,115,22,.15);border:1px solid rgba(249,115,22,.3);color:#fb923c;font-size:11px;font-weight:700;padding:4px 10px;border-radius:100px;letter-spacing:.06em;white-space:nowrap;align-self:flex-start}}
.rpt-hero{{padding:32px 36px;border-bottom:1px solid #f3f0ec;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}}
.rpt-trip{{font-size:20px;font-weight:800;letter-spacing:-.4px;margin-bottom:4px}}
.rpt-client{{font-size:13px;color:#78716c}}
.rpt-amount-block{{text-align:right;flex-shrink:0}}
.rpt-amount-label{{font-size:11px;font-weight:700;color:#78716c;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}}
.rpt-amount{{font-size:40px;font-weight:900;color:#059669;letter-spacing:-1.5px;line-height:1}}
.rpt-cpp{{font-size:12px;color:#78716c;margin-top:4px}}
.rpt-body{{padding:28px 36px}}
.rpt-section-label{{font-size:11px;font-weight:700;color:#a8a29e;letter-spacing:.10em;text-transform:uppercase;margin-bottom:14px;margin-top:24px}}
.rpt-section-label:first-child{{margin-top:0}}
.rpt-row{{display:flex;justify-content:space-between;align-items:baseline;padding:9px 0;border-bottom:1px solid #f5f3f0;font-size:14px;gap:16px}}
.rpt-row:last-of-type{{border-bottom:none}}
.rpt-row-label{{color:#78716c;flex-shrink:0}}
.rpt-row-val{{font-weight:500;text-align:right;color:#1c1917;font-variant-numeric:tabular-nums}}
.rpt-savings-row{{background:linear-gradient(90deg,rgba(5,150,105,.04),rgba(5,150,105,.08));border-radius:10px;padding:14px 16px!important;margin:16px 0;border:none!important}}
.rpt-savings-row .rpt-row-label{{font-weight:700;color:#065f46;font-size:15px}}
.rpt-savings-row .rpt-row-val{{font-size:20px;font-weight:900;color:#059669}}
.rpt-fee-row .rpt-row-val{{color:#d97706}}
.rpt-screenshot{{margin-top:20px}}
.rpt-screenshot img{{max-width:100%;border-radius:10px;border:1px solid #e7e5e4}}
.rpt-option{{background:#fafaf9;border:1px solid #e7e5e4;border-radius:10px;padding:16px;margin-top:4px;font-size:13px;color:#1c1917;line-height:1.6;white-space:pre-wrap;font-family:inherit}}
.rpt-foot{{background:#fafaf9;border-top:1px solid #f0ece8;padding:20px 36px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.rpt-foot-brand{{font-size:13px;font-weight:700;color:#a8a29e}}
.rpt-foot-brand span{{color:#f97316}}
.rpt-foot-note{{font-size:12px;color:#a8a29e;text-align:right;line-height:1.5}}
.rpt-print-btn{{display:inline-flex;align-items:center;gap:6px;background:#f97316;color:#fff;border:none;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;margin-top:16px}}
.rpt-print-btn:hover{{background:#ea6c0a}}
@media print{{body{{background:#fff}}.page{{margin:0;padding:0}}.card{{box-shadow:none;border-radius:0}}.rpt-print-btn{{display:none}}}}
@media(max-width:600px){{.rpt-head,.rpt-hero,.rpt-body,.rpt-foot{{padding:20px}}.rpt-amount{{font-size:32px}}.rpt-trip{{font-size:16px}}}}
</style>
</head>
<body>
<div class="page">
  <div class="card">
    <div class="rpt-head">
      <div>
        <div class="rpt-brand">District <span>Award</span> Travel</div>
        <div class="rpt-tagline">Award travel advisory · districtawardtravel@gmail.com</div>
      </div>
      <div class="rpt-badge">SAVINGS PROOF</div>
    </div>
    <div class="rpt-hero">
      <div>
        <div class="rpt-trip">{rec.trip_label or "Trip"}</div>
        <div class="rpt-client">Prepared for {client_name} · {date_str}</div>
      </div>
      <div class="rpt-amount-block">
        <div class="rpt-amount-label">You Saved</div>
        <div class="rpt-amount">{fmt_usd(gross)}</div>
        {'<div class="rpt-cpp">' + cpp_display + ' · ' + f"{rec.points_used:,}" + ' pts</div>' if rec.points_used else ''}
      </div>
    </div>
    <div class="rpt-body">
      <div class="rpt-section-label">Cash Benchmark</div>
      <div class="rpt-row"><span class="rpt-row-label">Cash price (verified)</span><span class="rpt-row-val">{fmt_usd(rec.cash_benchmark_cents)}</span></div>
      {'<div class="rpt-row"><span class="rpt-row-label">Source</span><span class="rpt-row-val" style="font-size:12px">' + rec.benchmark_source + '</span></div>' if rec.benchmark_source else ''}
      {'<div class="rpt-row"><span class="rpt-row-label">Assumptions</span><span class="rpt-row-val" style="font-size:12px;white-space:pre-wrap">' + rec.benchmark_assumptions + '</span></div>' if rec.benchmark_assumptions else ''}
      {('<div class="rpt-screenshot">' + screenshot_html + '</div>') if screenshot_html else ''}
      <div class="rpt-section-label">What You Paid</div>
      {'<div class="rpt-row"><span class="rpt-row-label">Points used</span><span class="rpt-row-val">' + f"{rec.points_used:,} {rec.points_program}".strip() + '</span></div>' if rec.points_used else ''}
      {'<div class="rpt-row"><span class="rpt-row-label">Award taxes + fees</span><span class="rpt-row-val">' + fmt_usd(rec.award_taxes_fees_cents) + '</span></div>' if rec.award_taxes_fees_cents else ''}
      {'<div class="rpt-row"><span class="rpt-row-label">Other out-of-pocket</span><span class="rpt-row-val">' + fmt_usd(rec.other_out_of_pocket_cents) + '</span></div>' if rec.other_out_of_pocket_cents else ''}
      {'<div class="rpt-section-label">Option Booked</div><div class="rpt-option">' + rec.option_booked + '</div>' if rec.option_booked else ''}
      <div class="rpt-row rpt-savings-row"><span class="rpt-row-label">Gross Savings</span><span class="rpt-row-val">{fmt_usd(gross)}</span></div>
      <div class="rpt-row rpt-fee-row"><span class="rpt-row-label">District Advisory Fee (10%)</span><span class="rpt-row-val">{fmt_usd(fee)}</span></div>
      {'<div class="rpt-row" style="font-weight:700"><span class="rpt-row-label">Invoice #</span><span class="rpt-row-val">' + rec.invoice_number + '</span></div>' if rec.invoice_number else ''}
      <button class="rpt-print-btn" onclick="window.print()">&#9113; Print / Save PDF</button>
    </div>
    <div class="rpt-foot">
      <div class="rpt-foot-brand">District <span>Award</span> Travel</div>
      <div class="rpt-foot-note">Benchmarks timestamped at research time. Savings = verified cash price − your out-of-pocket.<br>Advisory fee = 10% of gross savings, payable after booking.</div>
    </div>
  </div>
</div>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.get("/api/admin/intakes")
def list_intakes(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Intake).order_by(Intake.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": f"{r.first_name} {r.last_name}".strip(),
            "email": r.email,
            "phone": r.phone,
            "created_at": r.created_at.isoformat(),
            "payload": json.loads(r.payload or "{}"),
        }
        for r in rows
    ]


@app.delete("/api/admin/intakes/{intake_id}")
def delete_intake(intake_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete an intake request (typically test submissions or duplicates)."""
    intake = db.query(Intake).filter(Intake.id == intake_id).first()
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    db.delete(intake)
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────
# Phase 2 — Workflow / Trip Requests
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/board")
def get_board(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    now = dt.datetime.utcnow()
    trips = db.query(TripRequest).all()
    client_map = {c.id: c for c in db.query(Client).all()}
    columns = {s: [] for s in WORKFLOW_STATUSES}
    needs_attention = []
    for trip in trips:
        client = client_map.get(trip.client_id)
        row = _trip_row(trip, client, now)
        columns.setdefault(trip.workflow_status, []).append(row)
        if row["level"] in ("red", "amber") or row["follow_up"]:
            needs_attention.append(row)
        elif trip.workflow_status == "new":
            needs_attention.append(row)
    # sort needs_attention: reds first, then follow_up, then ambers, by hours desc
    def urgency_key(r):
        lvl = {"red": 0, "amber": 1, "ok": 2}.get(r["level"], 2)
        fu = 0 if r["follow_up"] else 1
        return (lvl, fu, -r["hours_in_stage"])
    needs_attention.sort(key=urgency_key)
    seen = set()
    deduped = []
    for r in needs_attention:
        if r["id"] not in seen:
            seen.add(r["id"])
            deduped.append(r)
    return {"columns": columns, "needs_attention": deduped}


@app.get("/api/admin/stats")
def admin_stats(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    now = dt.datetime.utcnow()
    stale_cutoff = now - dt.timedelta(hours=48)
    week_ago = now - dt.timedelta(days=7)
    terminal = {"closed", "declined", "lost", "booked"}

    trips = db.query(TripRequest).all()

    trips_by_status: dict = {}
    total_trips = 0
    active_trips = 0
    trips_stale = 0
    for t in trips:
        total_trips += 1
        s = t.workflow_status or "new"
        trips_by_status[s] = trips_by_status.get(s, 0) + 1
        if s not in terminal:
            active_trips += 1
            updated = t.last_activity_at or t.created_at
            if updated and updated < stale_cutoff:
                trips_stale += 1

    total_clients = db.query(Client).count()
    new_clients_this_week = db.query(Client).filter(Client.created_at >= week_ago).count()

    savings_recs = db.query(SavingsRecord).filter(
        SavingsRecord.status.in_(["booked", "invoiced", "paid"])
    ).all()
    total_savings_cents = 0
    total_fees_cents = 0
    for rec in savings_recs:
        gross = calc_gross_savings(
            rec.cash_benchmark_cents,
            rec.award_taxes_fees_cents,
            rec.other_out_of_pocket_cents,
        )
        total_savings_cents += max(gross, 0)
        total_fees_cents += calc_fee(gross, rec.fee_rate_bps)

    n_savings = len(savings_recs)
    avg_savings_per_trip_cents = (total_savings_cents // n_savings) if n_savings else 0

    return {
        "trips_by_status": trips_by_status,
        "total_clients": total_clients,
        "total_trips": total_trips,
        "active_trips": active_trips,
        "total_savings_cents": total_savings_cents,
        "total_fees_cents": total_fees_cents,
        "avg_savings_per_trip_cents": avg_savings_per_trip_cents,
        "trips_stale": trips_stale,
        "new_clients_this_week": new_clients_this_week,
    }


@app.get("/api/admin/trips")
def list_trips(client_email: Optional[str] = None, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    now = dt.datetime.utcnow()
    q = db.query(TripRequest)
    if client_email:
        client = db.query(Client).filter(Client.email == client_email.lower()).first()
        if not client:
            return []
        q = q.filter(TripRequest.client_id == client.id)
    trips = q.order_by(TripRequest.created_at.desc()).all()
    client_map = {c.id: c for c in db.query(Client).all()}
    return [_trip_row(t, client_map.get(t.client_id), now) for t in trips]


@app.post("/api/admin/trips")
def create_trip(body: TripCreateIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
    if not client:
        raise HTTPException(404, "Client not found")
    trip = TripRequest(
        client_id=client.id,
        destination=body.destination,
        origin=body.origin,
        dates=body.dates,
        passengers=body.passengers,
        cabin=body.cabin,
        flexibility=body.flexibility,
    )
    db.add(trip)
    db.flush()
    db.add(WorkflowEvent(trip_id=trip.id, from_status="", to_status="new"))
    db.commit()
    db.refresh(trip)
    return _trip_row(trip, client)


@app.patch("/api/admin/trips/{trip_id}")
def update_trip(trip_id: int, body: TripPatchIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(trip, field, val)
    trip.last_activity_at = dt.datetime.utcnow()
    db.commit()
    client = db.query(Client).filter(Client.id == trip.client_id).first()
    return _trip_row(trip, client)


@app.patch("/api/admin/trips/{trip_id}/status")
def advance_trip_status(trip_id: int, body: WorkflowAdvanceIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if not is_valid_workflow_transition(trip.workflow_status, body.new_status):
        raise HTTPException(400, f"Cannot transition from '{trip.workflow_status}' to '{body.new_status}'")
    if body.new_status in REASON_REQUIRED_STATUSES and not body.note.strip():
        raise HTTPException(422, "A reason is required when marking a trip declined or lost")
    old_status = trip.workflow_status
    trip.workflow_status = body.new_status
    trip.stage_entered_at = dt.datetime.utcnow()
    trip.last_activity_at = dt.datetime.utcnow()
    db.add(WorkflowEvent(trip_id=trip.id, from_status=old_status, to_status=body.new_status, note=body.note))
    db.commit()
    client = db.query(Client).filter(Client.id == trip.client_id).first()
    result = _trip_row(trip, client)
    if body.new_status == "booked":
        result["prompt_savings_record"] = True
    return result


NEXT_STATUS = {
    "new": "researching",
    "researching": "options_sent",
    "options_sent": "awaiting_decision",
    "awaiting_decision": "booked",
    "booked": "closed",
}


@app.post("/api/admin/trips/{trip_id}/advance")
def advance_trip_one_step(trip_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """Advance a trip to the next logical status (kanban one-click advance)."""
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    next_s = NEXT_STATUS.get(trip.workflow_status)
    if not next_s:
        raise HTTPException(400, f"No automatic next step from '{trip.workflow_status}'")
    old_status = trip.workflow_status
    trip.workflow_status = next_s
    trip.stage_entered_at = dt.datetime.utcnow()
    trip.last_activity_at = dt.datetime.utcnow()
    db.add(WorkflowEvent(trip_id=trip.id, from_status=old_status, to_status=next_s, note="Advanced via kanban"))
    db.commit()
    client = db.query(Client).filter(Client.id == trip.client_id).first()
    result = _trip_row(trip, client)
    if next_s == "booked":
        result["prompt_savings_record"] = True
    logger.info("trip.advance", extra={"trip_id": trip_id, "from": old_status, "to": next_s})
    if client and next_s in _CLIENT_STATUS_EMAILS:
        try:
            _notify_client_status_change(
                client_email=client.email or "",
                client_name=client.name or "",
                destination=trip.destination or "",
                new_status=next_s,
            )
        except Exception as exc:
            logger.error("trip.advance.notify_client.failed", extra={"trip_id": trip_id, "error": str(exc)})
    return result


@app.get("/api/admin/trips/{trip_id}/events")
def trip_events(trip_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    events = db.query(WorkflowEvent).filter(WorkflowEvent.trip_id == trip_id).order_by(WorkflowEvent.created_at.desc()).all()
    return [{"id": e.id, "from_status": e.from_status, "to_status": e.to_status, "note": e.note, "created_at": e.created_at.isoformat()} for e in events]


@app.patch("/api/admin/trips/{trip_id}/research-notes")
def update_trip_research_notes(trip_id: int, body: TripResearchNotesIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    trip.research_notes = body.research_notes
    trip.last_activity_at = dt.datetime.utcnow()
    db.commit()
    client = db.query(Client).filter(Client.id == trip.client_id).first()
    return _trip_row(trip, client)


@app.post("/api/admin/trips/{trip_id}/notes")
def add_trip_note(trip_id: int, body: TripNoteIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    notes = json.loads(trip.notes or "[]")
    notes.append({"text": body.text, "at": dt.datetime.utcnow().isoformat()})
    trip.notes = json.dumps(notes)
    trip.last_activity_at = dt.datetime.utcnow()
    db.commit()
    return {"ok": True, "notes": notes}


@app.post("/api/admin/trips/{trip_id}/time")
def add_trip_time(trip_id: int, body: TripTimeIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    trip.time_tracked_minutes = (trip.time_tracked_minutes or 0) + body.minutes
    db.commit()
    return {"ok": True, "time_tracked_minutes": trip.time_tracked_minutes}


@app.get("/api/admin/trips/{trip_id}/cockpit")
def trip_cockpit(trip_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    now = dt.datetime.utcnow()
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    client = db.query(Client).filter(Client.id == trip.client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")
    cdata = json.loads(client.data or "{}")
    points = cdata.get("points", [])
    program_names = [p.get("program", "") for p in points]
    templates = db.query(ResearchTemplate).filter(ResearchTemplate.active == 1).all()
    checklist = []
    for t in templates:
        if any(t.program.lower() in pn.lower() or pn.lower() in t.program.lower() for pn in program_names):
            checklist.append({"program": t.program, "portal_name": t.portal_name, "portal_url": t.portal_url})
    events = db.query(WorkflowEvent).filter(WorkflowEvent.trip_id == trip_id).order_by(WorkflowEvent.created_at.desc()).all()
    gf_query = urllib.parse.quote(f"flights from {trip.origin or 'origin'} to {trip.destination or 'destination'}")
    google_flights_url = f"https://www.google.com/travel/flights?q={gf_query}"
    effective_hourly_rate_cents = None
    if trip.savings_record_id and trip.time_tracked_minutes and trip.time_tracked_minutes > 0:
        sr = db.query(SavingsRecord).filter(SavingsRecord.id == trip.savings_record_id).first()
        if sr and sr.status == "paid":
            gross = calc_gross_savings(sr.cash_benchmark_cents, sr.award_taxes_fees_cents, sr.other_out_of_pocket_cents)
            fee = calc_fee(gross, sr.fee_rate_bps)
            effective_hourly_rate_cents = fee * 60 // trip.time_tracked_minutes
    return {
        "trip": _trip_row(trip, client, now),
        "client": {
            "name": client.name,
            "email": client.email,
            "points": points,
            "preferences": cdata.get("preferences", {}),
        },
        "events": [{"from_status": e.from_status, "to_status": e.to_status, "note": e.note, "created_at": e.created_at.isoformat()} for e in events],
        "research_checklist": checklist,
        "google_flights_url": google_flights_url,
        "effective_hourly_rate_cents": effective_hourly_rate_cents,
    }


@app.post("/api/admin/trips/{trip_id}/link-savings")
def link_savings(trip_id: int, body: LinkSavingsIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    trip = db.query(TripRequest).filter(TripRequest.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    sr = db.query(SavingsRecord).filter(SavingsRecord.id == body.savings_record_id).first()
    if not sr:
        raise HTTPException(404, "Savings record not found")
    if sr.client_id != trip.client_id:
        raise HTTPException(400, "Savings record belongs to a different client")
    trip.savings_record_id = body.savings_record_id
    db.commit()
    return {"ok": True}


@app.post("/api/admin/trips/import-legacy")
def import_legacy_trips(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    clients = db.query(Client).all()
    imported = 0
    for client in clients:
        cdata = json.loads(client.data or "{}")
        if cdata.get("_trips_imported"):
            continue
        for t in cdata.get("trips", []):
            trip = TripRequest(
                client_id=client.id,
                destination=t.get("destination", ""),
                dates=t.get("dates", ""),
                passengers=str(t.get("passengers", "1")),
                cabin=t.get("cabin", ""),
                flexibility=t.get("flexibility", ""),
                stage_entered_at=client.created_at,
                last_activity_at=client.created_at,
            )
            db.add(trip)
            db.flush()
            db.add(WorkflowEvent(trip_id=trip.id, from_status="", to_status="new", note="imported from legacy client data"))
            imported += 1
        cdata["_trips_imported"] = True
        client.data = json.dumps(cdata)
    db.commit()
    return {"ok": True, "imported": imported}


# ──────────────────────────────────────────────────────────────────────────
# Research Templates / Snippets / Message Templates
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/research-templates")
def list_research_templates(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rows = db.query(ResearchTemplate).order_by(ResearchTemplate.sort_order, ResearchTemplate.id).all()
    return [{"id": r.id, "program": r.program, "portal_name": r.portal_name, "portal_url": r.portal_url, "sort_order": r.sort_order, "active": r.active} for r in rows]


@app.post("/api/admin/research-templates")
def create_research_template(body: ResearchTemplateIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = ResearchTemplate(**body.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, **body.model_dump()}


@app.patch("/api/admin/research-templates/{tmpl_id}")
def update_research_template(tmpl_id: int, body: ResearchTemplatePatchIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = db.query(ResearchTemplate).filter(ResearchTemplate.id == tmpl_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(t, field, val)
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/research-templates/{tmpl_id}")
def delete_research_template(tmpl_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = db.query(ResearchTemplate).filter(ResearchTemplate.id == tmpl_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/snippets")
def list_snippets(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rows = db.query(Snippet).order_by(Snippet.category, Snippet.title).all()
    return [{"id": r.id, "title": r.title, "body": r.body, "category": r.category} for r in rows]


@app.post("/api/admin/snippets")
def create_snippet(body: SnippetIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    s = Snippet(**body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, **body.model_dump()}


@app.patch("/api/admin/snippets/{snippet_id}")
def update_snippet(snippet_id: int, body: SnippetPatchIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    s = db.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not s:
        raise HTTPException(404, "Snippet not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(s, field, val)
    s.updated_at = dt.datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/snippets/{snippet_id}")
def delete_snippet(snippet_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    s = db.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not s:
        raise HTTPException(404, "Snippet not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/templates")
def list_message_templates(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    rows = db.query(MessageTemplate).order_by(MessageTemplate.category, MessageTemplate.title).all()
    return [{"id": r.id, "category": r.category, "title": r.title, "subject": r.subject, "body": r.body} for r in rows]


@app.post("/api/admin/templates")
def create_message_template(body: MessageTemplateIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = MessageTemplate(**body.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, **body.model_dump()}


@app.patch("/api/admin/templates/{tmpl_id}")
def update_message_template(tmpl_id: int, body: MessageTemplatePatchIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tmpl_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(t, field, val)
    t.updated_at = dt.datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/templates/{tmpl_id}")
def delete_message_template(tmpl_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tmpl_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


@app.post("/api/admin/templates/{tmpl_id}/render")
def render_message_template(tmpl_id: int, body: TemplateRenderIn, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tmpl_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
    if not client:
        raise HTTPException(404, "Client not found")
    variables: dict = {"first_name": client.name.split()[0] if client.name else client.name}
    if body.trip_id:
        trip = db.query(TripRequest).filter(TripRequest.id == body.trip_id).first()
        if trip:
            variables["route"] = f"{trip.origin} → {trip.destination}" if trip.origin else trip.destination
            if trip.savings_record_id:
                sr = db.query(SavingsRecord).filter(SavingsRecord.id == trip.savings_record_id).first()
                if sr:
                    gross = calc_gross_savings(sr.cash_benchmark_cents, sr.award_taxes_fees_cents, sr.other_out_of_pocket_cents)
                    fee = calc_fee(gross, sr.fee_rate_bps)
                    def _fmt(c): return f"${abs(c) // 100:,}.{abs(c) % 100:02d}"
                    variables["savings_amount"] = _fmt(gross)
                    variables["fee_amount"] = _fmt(fee)
    return {"subject": render_template(t.subject, variables), "body": render_template(t.body, variables)}


# ──────────────────────────────────────────────────────────────────────────
# AI health
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/email-log")
def email_log_list(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """Last 100 outbound emails with delivery status — answers 'did the
    client actually get it?' without grepping server logs."""
    rows = db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(100).all()
    return [{
        "id": r.id, "recipient": r.recipient, "subject": r.subject,
        "status": r.status, "attempts": r.attempts, "last_error": r.last_error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    } for r in rows]


@app.get("/api/admin/ai-health")
def ai_health(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=24)
    rows = db.query(AIUsage).filter(AIUsage.created_at >= cutoff).all()
    by_provider: dict = {}
    for r in rows:
        p = by_provider.setdefault(r.provider, {"calls": 0, "failures": 0, "total_latency_ms": 0})
        p["calls"] += 1
        if not r.success:
            p["failures"] += 1
        p["total_latency_ms"] += r.latency_ms
    stats = {}
    for prov, p in by_provider.items():
        stats[prov] = {
            "calls_24h": p["calls"],
            "failures_24h": p["failures"],
            "avg_latency_ms": p["total_latency_ms"] // p["calls"] if p["calls"] else 0,
        }
    providers_configured = {
        "gemini": bool(GEMINI_API_KEY),
        "groq": bool(GROQ_API_KEY),
        "seats_aero": bool(SEATS_AERO_API_KEY),
    }
    return {"providers_configured": providers_configured, "stats_24h": stats, "breakers": ai_client.get_health()}


# ──────────────────────────────────────────────────────────────────────────
# Daily ops digest
# ──────────────────────────────────────────────────────────────────────────

def build_digest(db: Session, now=None) -> dict:
    ET = ZoneInfo("America/New_York")
    now = now or dt.datetime.utcnow()
    since_24h = now - dt.timedelta(hours=24)
    new_intakes = db.query(Intake).filter(Intake.created_at >= since_24h).count()
    total_intakes = db.query(Intake).count()
    trips = db.query(TripRequest).filter(TripRequest.workflow_status.notin_(["closed", "declined", "lost"])).all()
    client_map = {c.id: c for c in db.query(Client).all()}
    stale_cards = []
    awaiting = []
    for trip in trips:
        flags = trip_attention_flags(trip.workflow_status, trip.stage_entered_at, trip.last_activity_at, now)
        if flags["level"] in ("red", "amber") or flags["follow_up"]:
            client = client_map.get(trip.client_id)
            stale_cards.append({
                "client": client.name if client else "?",
                "destination": trip.destination,
                "status": trip.workflow_status,
                "hours_in_stage": flags["hours_in_stage"],
                "level": flags["level"],
            })
        if trip.workflow_status == "awaiting_decision":
            client = client_map.get(trip.client_id)
            awaiting.append({"client": client.name if client else "?", "destination": trip.destination})
    invoiced = db.query(SavingsRecord).filter(SavingsRecord.status == "invoiced").all()
    invoiced_list = []
    for r in invoiced:
        client = client_map.get(r.client_id)
        gross = calc_gross_savings(r.cash_benchmark_cents, r.award_taxes_fees_cents, r.other_out_of_pocket_cents)
        fee = calc_fee(gross, r.fee_rate_bps)
        invoiced_list.append({"invoice_number": r.invoice_number, "client": client.name if client else "?", "fee_cents": fee})
    events_24h = db.query(WorkflowEvent).filter(WorkflowEvent.created_at >= since_24h).count()
    return {
        "generated_at_et": now.astimezone(ET).isoformat(),
        "new_intakes_24h": new_intakes,
        "total_pending_intakes": total_intakes,
        "stale_trips": stale_cards,
        "awaiting_decision_trips": awaiting,
        "outstanding_invoices": invoiced_list,
        "workflow_events_24h": events_24h,
    }


@app.get("/api/admin/digest")
def get_digest(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    return build_digest(db)


CRON_SECRET = os.environ.get("CRON_SECRET", "")


@app.post("/api/cron/digest")
def cron_digest(key: str = "", db: Session = Depends(get_db)):
    if not CRON_SECRET:
        raise HTTPException(503, "Digest cron not configured — set CRON_SECRET env var")
    if not hmac.compare_digest(key, CRON_SECRET):
        raise HTTPException(403, "Invalid cron key")
    digest = build_digest(db)
    ET = ZoneInfo("America/New_York")
    lines = [
        f"District Award Travel — Daily Digest",
        f"Generated: {digest['generated_at_et']}",
        "",
        f"NEW INTAKES: {digest['new_intakes_24h']} in last 24h ({digest['total_pending_intakes']} total pending)",
        "",
    ]
    if digest["stale_trips"]:
        lines.append("NEEDS ATTENTION:")
        for t in digest["stale_trips"]:
            lines.append(f"  [{t['level'].upper()}] {t['client']} — {t['destination']} ({t['status']}, {t['hours_in_stage']}h in stage)")
        lines.append("")
    if digest["awaiting_decision_trips"]:
        lines.append("AWAITING DECISION:")
        for t in digest["awaiting_decision_trips"]:
            lines.append(f"  {t['client']} — {t['destination']}")
        lines.append("")
    if digest["outstanding_invoices"]:
        lines.append("OUTSTANDING INVOICES:")
        for inv in digest["outstanding_invoices"]:
            fee_str = f"${inv['fee_cents'] // 100:,}.{inv['fee_cents'] % 100:02d}"
            lines.append(f"  {inv['invoice_number']} — {inv['client']} — {fee_str}")
        lines.append("")
    lines.append(f"Workflow events in last 24h: {digest['workflow_events_24h']}")
    sent = send_email("DAT Daily Digest", "\n".join(lines))
    return {"ok": True, "sent": sent}


# ──────────────────────────────────────────────────────────────────────────
# Static website (served last so /api routes take precedence)
# ──────────────────────────────────────────────────────────────────────────
if os.path.isdir(PUBLIC_DIR):
    @app.get("/")
    def root():
        return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="site")
else:
    @app.get("/")
    def root_fallback():
        return JSONResponse({"message": "DAT API running. Static site directory not found."})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
