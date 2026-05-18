"""
District Award Travel — Morning Briefing Generator
Runs as the final step of the nightly GitHub Actions workflow.
Compiles what all three engineers built and sends a summary email.
Falls back to saving an HTML file if email is not configured.
"""

import os
import json
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TASKS_FILE = BASE_DIR / "tasks" / "backlog.json"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def load_backlog():
    with open(TASKS_FILE) as f:
        return json.load(f)


def get_todays_completions(backlog):
    return [
        t for t in backlog["backlog"]
        if t.get("completed_at") == TODAY and t.get("status") == "completed"
    ]


def get_pending_count(backlog):
    return len([t for t in backlog["backlog"] if t.get("status") == "pending"])


def read_alerts():
    alerts_file = BASE_DIR / "tasks" / "alerts.json"
    if alerts_file.exists():
        with open(alerts_file) as f:
            data = json.load(f)
        return data.get("alerts", [])
    return []


def read_transfer_bonuses():
    bonuses_file = BASE_DIR / "tasks" / "transfer_bonuses.json"
    if bonuses_file.exists():
        with open(bonuses_file) as f:
            return json.load(f)
    return {}


def build_html_report(backlog, completions, pending_count, alerts, bonuses):
    engineer_sections = {
        "marcus": {"name": "Marcus Webb", "emoji": "🔧", "color": "#00ff88", "tasks": []},
        "jordan": {"name": "Jordan Reyes", "emoji": "🤖", "color": "#00aaff", "tasks": []},
        "priya":  {"name": "Priya Kapoor",  "emoji": "🎨", "color": "#9b59ff", "tasks": []},
    }

    for task in completions:
        eng = task.get("assigned_to")
        if eng in engineer_sections:
            engineer_sections[eng]["tasks"].append(task)

    eng_html = ""
    for eng_id, eng in engineer_sections.items():
        tasks_html = ""
        if eng["tasks"]:
            for t in eng["tasks"]:
                summary = t.get("completion_summary", "Task completed.")
                tasks_html += f"""
                <div style="background:#0f1621;border:1px solid #1a2540;border-left:3px solid {eng['color']};border-radius:6px;padding:12px 16px;margin-bottom:8px;">
                  <div style="font-size:11px;color:#7a8ba0;font-family:monospace;margin-bottom:4px;">{t['id']} · {t['priority'].upper()}</div>
                  <div style="font-size:13px;color:#e8edf5;font-weight:600;margin-bottom:6px;">{t['title']}</div>
                  <div style="font-size:12px;color:#7a8ba0;line-height:1.5;">{summary}</div>
                </div>"""
        else:
            tasks_html = '<div style="font-size:12px;color:#3d5068;font-family:monospace;">No tasks completed tonight — all caught up or tasks in progress.</div>'

        eng_html += f"""
        <div style="margin-bottom:24px;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <span style="font-size:18px;">{eng['emoji']}</span>
            <div>
              <div style="font-size:13px;font-weight:700;color:{eng['color']}">{eng['name']}</div>
              <div style="font-size:10px;color:#3d5068;font-family:monospace;letter-spacing:.08em;">
                {len(eng['tasks'])} TASK(S) COMPLETED TONIGHT
              </div>
            </div>
          </div>
          {tasks_html}
        </div>"""

    alerts_html = ""
    if alerts:
        for a in alerts[:5]:
            alerts_html += f"""
            <div style="background:#0f1621;border:1px solid rgba(0,255,136,.2);border-radius:6px;padding:10px 14px;margin-bottom:6px;">
              <span style="color:#00ff88;font-family:monospace;font-size:11px;">▸ {a.get('message','')}</span>
            </div>"""
    else:
        alerts_html = '<div style="color:#3d5068;font-family:monospace;font-size:11px;">No new alerts from overnight session.</div>'

    total_completed = len(completions)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>DAT Morning Brief — {TODAY}</title></head>
<body style="background:#080c10;color:#e8edf5;font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:0;">
  <div style="max-width:680px;margin:0 auto;padding:32px 24px;">

    <!-- Header -->
    <div style="background:#0f1621;border:1px solid #1a2540;border-radius:12px;padding:24px;margin-bottom:24px;border-top:3px solid #00ff88;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <span style="font-size:24px;">✈</span>
        <div>
          <div style="font-size:18px;font-weight:800;color:#00ff88;">District Award Travel</div>
          <div style="font-size:10px;color:#7a8ba0;font-family:monospace;letter-spacing:.1em;">MORNING BRIEFING · {NOW}</div>
        </div>
      </div>
      <div style="color:#7a8ba0;font-size:13px;margin-top:8px;">
        Your engineers worked through the night. Here is what they built.
      </div>
    </div>

    <!-- Stats Row -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;">
      <div style="background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:700;color:#00ff88;font-family:monospace;">{total_completed}</div>
        <div style="font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;">Tasks Built</div>
      </div>
      <div style="background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:700;color:#00aaff;font-family:monospace;">{pending_count}</div>
        <div style="font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;">Tasks Pending</div>
      </div>
      <div style="background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:700;color:#ffd700;font-family:monospace;">{len(alerts)}</div>
        <div style="font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;">New Alerts</div>
      </div>
    </div>

    <!-- Engineer Work -->
    <div style="margin-bottom:8px;font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;">
      ── Engineering Activity
    </div>
    {eng_html}

    <!-- Alerts -->
    <div style="margin-bottom:8px;margin-top:24px;font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;">
      ── Award Alerts & Opportunities
    </div>
    {alerts_html}

    <!-- Footer -->
    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #1a2540;font-size:10px;color:#3d5068;font-family:monospace;text-align:center;">
      District Award Travel · Autonomous Engineering System · Engineers: Marcus · Jordan · Priya
    </div>

  </div>
</body>
</html>"""


def send_email(html_content):
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_user = os.environ.get("SMTP_USERNAME") or os.environ.get("REPORT_EMAIL")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    report_email = os.environ.get("REPORT_EMAIL")

    if not all([smtp_server, smtp_user, smtp_pass, report_email]):
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"DAT Morning Brief — {TODAY}"
        msg["From"] = smtp_user
        msg["To"] = report_email
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_server, 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, report_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


def main():
    backlog = load_backlog()
    completions = get_todays_completions(backlog)
    pending_count = get_pending_count(backlog)
    alerts = read_alerts()
    bonuses = read_transfer_bonuses()

    html = build_html_report(backlog, completions, pending_count, alerts, bonuses)

    # Save HTML brief to logs/
    brief_path = LOGS_DIR / f"morning_brief_{TODAY}.html"
    brief_path.write_text(html)
    print(f"Morning brief saved: {brief_path}")

    # Also save plain text version
    txt_path = LOGS_DIR / f"morning_brief_{TODAY}.txt"
    txt_lines = [
        f"DISTRICT AWARD TRAVEL — MORNING BRIEF",
        f"Date: {TODAY} · {NOW}",
        "=" * 50,
        f"Tasks completed tonight: {len(completions)}",
        f"Tasks still pending: {pending_count}",
        f"New alerts: {len(alerts)}",
        "",
        "COMPLETED TASKS:",
    ]
    for t in completions:
        txt_lines.append(f"  [{t['assigned_to'].upper()}] {t['id']}: {t['title']}")
        if t.get("completion_summary"):
            txt_lines.append(f"    → {t['completion_summary']}")
    txt_path.write_text("\n".join(txt_lines))

    # Attempt email send
    if send_email(html):
        print(f"Morning brief emailed to {os.environ.get('REPORT_EMAIL')}")
    else:
        print("Email not configured — brief saved to logs/ only.")


if __name__ == "__main__":
    main()
