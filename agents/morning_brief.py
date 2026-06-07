"""
District Award Travel — Daily Ops Briefing
==========================================
Reads data/action_items.json, works out what's due (and how soon), and emails
Braden a prioritized morning summary so nothing slips through the cracks —
especially time-sensitive bookings like the Casa di Langa Amex FHR deadline.

Email is sent via Gmail SMTP using the same credentials as the backend:
  GMAIL_USER            districtawardtravel@gmail.com
  GMAIL_APP_PASSWORD    16-char Google App Password
  NOTIFY_EMAIL          where the briefing goes (defaults to GMAIL_USER)

Set those three as GitHub Actions secrets. With none set, it just prints the
briefing to the workflow log (still useful, just no email).
"""

import os
import json
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / "data" / "action_items.json"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

TODAY = datetime.date.today()
TODAY_STR = TODAY.isoformat()
NOW = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_COLOR = {"critical": "#ff4d6d", "high": "#f5c842", "medium": "#38b6ff", "low": "#8896a6"}


def load_items():
    if not DATA_FILE.exists():
        return {"clients": []}
    with open(DATA_FILE) as f:
        return json.load(f)


def flatten(data):
    """Return a flat list of action items with computed days-until-due."""
    rows = []
    for client in data.get("clients", []):
        for item in client.get("items", []):
            due_str = item.get("due", "")
            days = None
            try:
                due = datetime.date.fromisoformat(due_str)
                days = (due - TODAY).days
            except ValueError:
                pass
            rows.append({
                "client": client.get("name", "Unknown"),
                "title": item.get("title", ""),
                "detail": item.get("detail", ""),
                "priority": item.get("priority", "low"),
                "due": due_str,
                "days": days,
            })
    # Sort: overdue/soonest first, then by priority
    def sort_key(r):
        days = r["days"] if r["days"] is not None else 9999
        return (days, PRIORITY_RANK.get(r["priority"], 9))
    return sorted(rows, key=sort_key)


def urgency_label(days):
    if days is None:
        return "No date"
    if days < 0:
        return f"OVERDUE by {abs(days)}d"
    if days == 0:
        return "DUE TODAY"
    if days == 1:
        return "Due tomorrow"
    if days <= 14:
        return f"Due in {days} days"
    return f"Due in {days} days"


def build_html(rows):
    urgent = [r for r in rows if r["days"] is not None and r["days"] <= 14]
    cards = ""
    for r in rows:
        color = PRIORITY_COLOR.get(r["priority"], "#8896a6")
        label = urgency_label(r["days"])
        soon = r["days"] is not None and r["days"] <= 7
        label_color = "#ff4d6d" if (r["days"] is not None and r["days"] <= 7) else "#8896a6"
        cards += (
            "<div style='background:#0f1621;border:1px solid #1a2540;border-left:3px solid " + color + ";border-radius:8px;padding:14px 18px;margin-bottom:10px;'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;'>"
            "<span style='font-size:10px;color:#7a8ba0;font-family:monospace;text-transform:uppercase;letter-spacing:.06em;'>" + r["client"] + " · " + r["priority"].upper() + "</span>"
            "<span style='font-size:11px;font-weight:700;color:" + label_color + ";font-family:monospace;'>" + label + (" · " + r["due"] if r["due"] else "") + "</span>"
            "</div>"
            "<div style='font-size:14px;color:#e8edf5;font-weight:600;margin:6px 0 3px;'>" + r["title"] + "</div>"
            "<div style='font-size:12px;color:#8896a6;line-height:1.5;'>" + r["detail"] + "</div>"
            "</div>"
        )
    if not cards:
        cards = "<div style='color:#3d5068;font-family:monospace;font-size:12px;'>No open action items. Enjoy the clear runway. ✈</div>"

    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<title>DAT Daily Briefing — " + TODAY_STR + "</title></head>"
        "<body style='background:#080c10;color:#e8edf5;font-family:Segoe UI,sans-serif;margin:0;padding:0;'>"
        "<div style='max-width:680px;margin:0 auto;padding:32px 24px;'>"

        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:12px;padding:24px;margin-bottom:24px;border-top:3px solid #00e87a;'>"
        "<div style='font-size:22px;font-weight:800;color:#00e87a;'>✈ District Award Travel</div>"
        "<div style='font-size:11px;color:#7a8ba0;font-family:monospace;margin-top:4px;'>DAILY OPS BRIEFING · " + NOW + "</div>"
        "<div style='color:#8896a6;font-size:13px;margin-top:10px;'>Good morning, Braden. Here's what needs your attention today.</div>"
        "</div>"

        "<div style='display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:28px;'>"
        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:16px;text-align:center;'>"
        "<div style='font-size:30px;font-weight:700;color:#ff4d6d;font-family:monospace;'>" + str(len(urgent)) + "</div>"
        "<div style='font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;'>Due Within 2 Weeks</div></div>"
        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:16px;text-align:center;'>"
        "<div style='font-size:30px;font-weight:700;color:#38b6ff;font-family:monospace;'>" + str(len(rows)) + "</div>"
        "<div style='font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;'>Total Open Items</div></div>"
        "</div>"

        "<div style='font-size:9px;color:#00e87a;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;margin-bottom:14px;'>── Action Items (soonest first)</div>"
        + cards +

        "<div style='margin-top:32px;padding-top:16px;border-top:1px solid #1a2540;font-size:10px;color:#3d5068;font-family:monospace;text-align:center;'>"
        "District Award Travel · Daily Ops Briefing · edit data/action_items.json to update"
        "</div></div></body></html>"
    )


def build_text(rows):
    lines = ["DISTRICT AWARD TRAVEL — DAILY OPS BRIEFING", NOW, ""]
    for r in rows:
        lines.append(f"[{r['priority'].upper()}] {r['client']}: {r['title']}")
        lines.append(f"    {urgency_label(r['days'])}" + (f" ({r['due']})" if r['due'] else ""))
        lines.append(f"    {r['detail']}")
        lines.append("")
    if not rows:
        lines.append("No open action items.")
    return "\n".join(lines)


def send_email(html_content, text_content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    notify = os.environ.get("NOTIFY_EMAIL", gmail_user)

    if not all([gmail_user, gmail_pass, notify]):
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping email (briefing printed above).")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "DAT Daily Briefing — " + TODAY_STR
        msg["From"] = "District Award Travel <" + gmail_user + ">"
        msg["To"] = notify
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [notify], msg.as_string())
        print("Daily briefing emailed to " + notify)
        return True
    except Exception as e:
        print("Email failed: " + str(e))
        return False


def main():
    data = load_items()
    rows = flatten(data)

    html = build_html(rows)
    text = build_text(rows)

    brief_path = LOGS_DIR / ("daily_brief_" + TODAY_STR + ".html")
    brief_path.write_text(html)

    print("=" * 56)
    print(text)
    print("=" * 56)
    print("Saved: " + str(brief_path))

    send_email(html, text)


if __name__ == "__main__":
    main()
