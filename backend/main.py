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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SEATS_AERO_API_KEY = os.environ.get("SEATS_AERO_API_KEY", "")

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
    """Send a plain-text email to the admin notify address."""
    return send_email_to(NOTIFY_EMAIL, subject, body, reply_to=reply_to)


def send_email_to(to: str, subject: str, body: str, reply_to: str = "") -> bool:
    """Send a plain-text email via Gmail SMTP to any address. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping send.")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = f"District Award Travel <{GMAIL_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [to], msg.as_string())
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


# ── Diagnostics (safe: never reveals the password itself) ──
@app.get("/api/admin/diag")
def admin_diag(db: Session = Depends(get_db)):
    """Tells us whether the admin exists and whether the env-var password
    actually matches the stored hash — so we can pinpoint a login failure
    without leaking any secret. Reports the password LENGTH only."""
    admin = db.query(Admin).filter(Admin.email == ADMIN_EMAIL).first()
    return {
        "expected_login_email": ADMIN_EMAIL,
        "admin_exists": admin is not None,
        "db_type": "postgres" if DATABASE_URL.startswith("postgresql") else "sqlite",
        "env_password_length": len(ADMIN_PASSWORD),
        "env_password_matches_stored": (
            verify_pw(ADMIN_PASSWORD, admin.password_hash) if admin else None
        ),
    }


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
        try:
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
            parsed = json.loads(content)
            return {"ok": True, "source": "groq", "data": parsed}
        except Exception as e:
            print(f"[groq] parse failed: {e}")
            # fall through to Gemini

    if GEMINI_API_KEY:
        try:
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
            parsed = json.loads(content)
            return {"ok": True, "source": "gemini", "data": parsed}
        except Exception as e:
            print(f"[gemini] parse failed: {e}")

    # No AI key configured — return empty stub so UI still works
    return {"ok": True, "source": "none", "data": {
        "first_name": None, "last_name": None, "email": None, "phone": None,
        "home_airport": None, "travel_goals": None, "trips": [], "points": [],
        "cabin_pref": None, "notes": raw[:300],
    }}


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


@app.post("/api/setup/admin")
def setup_admin(body: LoginIn, db: Session = Depends(get_db)):
    """Create the first admin account. Only works if no admins exist yet."""
    existing = db.query(Admin).first()
    if existing:
        raise HTTPException(status_code=403, detail="Admin already exists. Use normal login.")
    admin = Admin(
        email=body.email.lower(),
        password_hash=hash_pw(body.password),
        name=body.email.split("@")[0].title(),
    )
    db.add(admin)
    db.commit()
    return {"ok": True, "message": "Admin account created. You can now log in normally."}


@app.post("/api/setup/sync-password")
def sync_admin_password(db: Session = Depends(get_db)):
    """Sync admin password with ADMIN_PASSWORD env var. Use if stuck on login."""
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password:
        raise HTTPException(status_code=400, detail="ADMIN_PASSWORD env var not set")
    admin = db.query(Admin).filter(Admin.email == "admin@districtawardtravel.com").first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found")
    admin.password_hash = hash_pw(admin_password)
    db.commit()
    return {"ok": True, "message": "Admin password synced with env var. Try signing in again."}



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


class UpdateClientDataIn(BaseModel):
    data: dict


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
    return {"ok": True}


@app.delete("/api/admin/clients/{email}")
def delete_client(email: str, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Permanently delete a client record. Use only for test/duplicate accounts."""
    client = db.query(Client).filter(Client.email == email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"ok": True}


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

    # Also send email notification
    send_email_to(
        client.email,
        f"New message: {msg_in.subject}",
        f"Hi {client.name.split()[0]},\n\n{msg_in.body}\n\nLog in to your portal to view this message.\n\nBest,\nBraden\nDistrict Award Travel"
    )

    return {"ok": True, "message_id": len(messages) - 1}


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
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")

    try:
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
        extracted = json.loads(content)
    except Exception as e:
        print(f"[gemini-vision] scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini Vision scan failed: {e}")

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
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")

    client = db.query(Client).filter(Client.email == body.client_email.lower()).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

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

    try:
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
        recs = json.loads(content)
    except Exception as e:
        print(f"[gemini] sweet spots failed: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {e}")

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
                    print(f"[seats.aero] {rec.get('destination')}: {e2}")

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
        try:
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
            parsed = json.loads(content)
            return {"ok": True, "source": "groq", "data": parsed}
        except Exception as e:
            print(f"[groq] thread parse failed: {e}")

    if GEMINI_API_KEY:
        try:
            import httpx
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": THREAD_PARSE_PROMPT + raw}]}]},
                timeout=25,
            )
            resp.raise_for_status()
            content = strip_fences(resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
            parsed = json.loads(content)
            return {"ok": True, "source": "gemini", "data": parsed}
        except Exception as e:
            print(f"[gemini] thread parse failed: {e}")

    return {"ok": True, "source": "none", "data": {
        "first_name": None, "last_name": None, "email": None, "phone": None,
        "home_airport": None, "travel_goals": None, "trips": [], "points": [],
        "cabin_pref": None, "notes": raw[:300],
        "conversation_summary": "AI not available — review manually.",
        "action_items": [],
    }}


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
