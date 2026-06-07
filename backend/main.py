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
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ──────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24 * 7  # one week

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@districtawardtravel.com").lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "dat2026")

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", GMAIL_USER or "districtawardtravel@gmail.com")

# Render gives a postgres:// URL; SQLAlchemy needs postgresql://
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./dat.db"

# Path to the static website files
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.normpath(os.path.join(HERE, "..", "platform", "public"))

# ──────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
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
    created_at = Column(DateTime, default=dt.datetime.utcnow)


Base.metadata.create_all(bind=engine)


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
# Email
# ──────────────────────────────────────────────────────────────────────────
def send_email(subject: str, body: str, reply_to: str = "") -> bool:
    """Send a plain-text email via Gmail SMTP. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping send.")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = f"District Award Travel <{GMAIL_USER}>"
        msg["To"] = NOTIFY_EMAIL
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [NOTIFY_EMAIL], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# ── Health ──
@app.get("/api/health")
def health():
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat()}


# ── Intake ──
@app.post("/api/intake")
async def submit_intake(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    rec = Intake(
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        payload=json.dumps(data),
    )
    db.add(rec)
    db.commit()
    name = f"{data.get('first_name','')} {data.get('last_name','')}".strip() or "Someone"
    send_email(
        subject=f"New DAT Intake: {name}",
        body=format_intake_email(data),
        reply_to=data.get("email", ""),
    )
    return {"ok": True, "id": rec.id}


# ── Auth ──
@app.post("/api/admin/login")
def admin_login(body: LoginIn, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == body.email.lower()).first()
    if not admin or not verify_pw(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(admin.email, "admin"), "name": admin.name, "role": "admin"}


@app.post("/api/auth/login")
def client_login(body: LoginIn, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.email == body.email.lower()).first()
    if not client or not verify_pw(body.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(client.email, "client"), "name": client.name, "role": "client"}


# ── Client self ──
@app.get("/api/client/me")
def client_me(identity: dict = Depends(current_identity), db: Session = Depends(get_db)):
    if identity.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    client = db.query(Client).filter(Client.email == identity["sub"]).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = json.loads(client.data or "{}")
    payload.update({"name": client.name, "tier": client.tier, "email": client.email})
    return payload


# ── Admin: client management ──
@app.get("/api/admin/clients")
def list_clients(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return [
        {"email": c.email, "name": c.name, "tier": c.tier, "created_at": c.created_at.isoformat()}
        for c in clients
    ]


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
