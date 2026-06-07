# District Award Travel — Backend

A self-contained FastAPI backend that serves the website **and** provides:

- **Intake submissions** → stored in the database + emailed to you
- **Client login** → clients sign into their portal
- **Admin login** → you sign into the admin dashboard
- **Client management** → create/list clients, view intake submissions

Everything runs as **one** service. Deploy it free on Render with a free
PostgreSQL database.

---

## Run it locally (optional — to test before deploying)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Then open http://localhost:8000 — the full website loads, and the API lives
under `/api/*`. With no env vars set, it uses a local `dat.db` SQLite file and
the default admin login `admin@districtawardtravel.com` / `dat2026`.

---

## Deploy to Render (free) — step by step

### 1. Get a Gmail App Password (for sending intake emails)

Gmail blocks normal passwords for apps, so you need a 16-character **App Password**:

1. Go to https://myaccount.google.com/security
2. Turn on **2-Step Verification** if it isn't already
3. Go to https://myaccount.google.com/apppasswords
4. Create an app password named "DAT Backend" → copy the 16-character code
   (looks like `abcd efgh ijkl mnop` — you can paste it with or without spaces)

### 2. Push this repo to GitHub

The branch with this backend must be merged into `main` (or point Render at the
branch directly).

### 3. Create the service on Render

1. Sign up free at https://render.com (log in with GitHub)
2. Click **New +** → **Blueprint**
3. Connect this repository
4. Render reads `render.yaml` and proposes a **web service** + a **PostgreSQL
   database**. Click **Apply**.

### 4. Set your two secret env vars

In the Render dashboard → your service → **Environment**, fill in the two
values marked "set this yourself":

| Variable | Value |
|---|---|
| `ADMIN_PASSWORD` | the password you want for the admin dashboard |
| `GMAIL_APP_PASSWORD` | the 16-character code from step 1 |

Then click **Manual Deploy → Deploy latest commit**.

### 5. You're live

Render gives you a URL like `https://district-award-travel.onrender.com`.

- Website: that URL
- Admin: that URL + `/admin.html`
- Intake emails will arrive at `districtawardtravel@gmail.com`

> **Note on the free tier:** the service "sleeps" after 15 minutes of no
> traffic and takes ~30 seconds to wake on the next visit. Fine for launch;
> upgrade to the $7/mo plan later if you want it always-on.

---

## Environment variables reference

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | auto | Signs login tokens (Render generates it) |
| `DATABASE_URL` | auto | Postgres connection (Render provides it) |
| `ADMIN_EMAIL` | yes | Admin login email |
| `ADMIN_PASSWORD` | yes | Admin login password (seeds the admin on first boot) |
| `GMAIL_USER` | for email | `districtawardtravel@gmail.com` |
| `GMAIL_APP_PASSWORD` | for email | 16-char Google App Password |
| `NOTIFY_EMAIL` | optional | Where intake emails go (defaults to `GMAIL_USER`) |

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | Health check |
| POST | `/api/intake` | none | Submit intake form |
| POST | `/api/admin/login` | none | Admin login → token |
| POST | `/api/auth/login` | none | Client login → token |
| GET | `/api/client/me` | client | Logged-in client's portal data |
| GET | `/api/admin/clients` | admin | List all clients |
| POST | `/api/admin/clients` | admin | Create a client |
| GET | `/api/admin/intakes` | admin | List intake submissions |
