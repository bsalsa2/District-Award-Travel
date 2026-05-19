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
        t for t in backlog.get("backlog", [])
        if t.get("completed_at") == TODAY and t.get("status") == "completed"
    ]


def get_pending_tasks(backlog):
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks = [t for t in backlog.get("backlog", []) if t.get("status") == "pending"]
    return sorted(tasks, key=lambda t: order.get(t.get("priority", "low"), 9))


def build_html_report(backlog, completions, pending_tasks):
    engineer_sections = {
        "mitchell": {"name": "Mitchell Hashimoto", "role": "Infrastructure Engineer", "emoji": "🏗️", "color": "#00ff88", "tasks": []},
        "martin":   {"name": "Martin Thompson",    "role": "Backend Engineer",         "emoji": "⚡", "color": "#00aaff", "tasks": []},
        "jeff":     {"name": "Jeff Dean",           "role": "AI & Full-Stack Engineer", "emoji": "🧠", "color": "#9b59ff", "tasks": []},
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
                files = t.get("files_created", [])
                files_str = " · ".join([f.split("/")[-1] for f in files[:4]]) if files else ""
                files_html = ("<div style=\"font-size:10px;color:#3d5068;font-family:monospace;margin-top:6px;\">FILES: " + files_str + "</div>") if files_str else ""
                tasks_html += (
                    "<div style=\"background:#0f1621;border:1px solid #1a2540;border-left:3px solid " + eng["color"] + ";border-radius:6px;padding:12px 16px;margin-bottom:8px;\">"
                    "<div style=\"font-size:11px;color:#7a8ba0;font-family:monospace;margin-bottom:4px;\">" + t["id"] + " · " + t.get("priority", "").upper() + "</div>"
                    "<div style=\"font-size:13px;color:#e8edf5;font-weight:600;margin-bottom:6px;\">" + t["title"] + "</div>"
                    "<div style=\"font-size:12px;color:#7a8ba0;line-height:1.5;\">" + summary + "</div>"
                    + files_html + "</div>"
                )
        else:
            tasks_html = "<div style=\"font-size:12px;color:#3d5068;font-family:monospace;\">No tasks completed tonight.</div>"

        eng_html += (
            "<div style=\"margin-bottom:24px;\">"
            "<div style=\"display:flex;align-items:center;gap:8px;margin-bottom:12px;\">"
            "<span style=\"font-size:18px;\">" + eng["emoji"] + "</span>"
            "<div>"
            "<div style=\"font-size:13px;font-weight:700;color:" + eng["color"] + ";\">" + eng["name"] + "</div>"
            "<div style=\"font-size:10px;color:#3d5068;font-family:monospace;letter-spacing:.08em;\">"
            + eng["role"].upper() + " · " + str(len(eng["tasks"])) + " TASK(S) TONIGHT"
            + "</div></div></div>" + tasks_html + "</div>"
        )

    plan_html = ""
    shown = set()
    for t in pending_tasks:
        eng_id = t.get("assigned_to")
        if eng_id in engineer_sections and eng_id not in shown:
            eng = engineer_sections[eng_id]
            plan_html += (
                "<div style=\"background:#0f1621;border:1px solid #1a2540;border-left:3px solid " + eng["color"] + ";border-radius:6px;padding:10px 14px;margin-bottom:6px;\">"
                "<div style=\"font-size:10px;color:#3d5068;font-family:monospace;margin-bottom:3px;\">" + eng["name"].upper() + " · " + t.get("priority", "").upper() + "</div>"
                "<div style=\"font-size:12px;color:#e8edf5;\">" + t["title"] + "</div>"
                "</div>"
            )
            shown.add(eng_id)

    if not plan_html:
        plan_html = "<div style=\"color:#3d5068;font-family:monospace;font-size:11px;\">Engineers will generate new tasks from tonight's work.</div>"

    total_completed = len(completions)
    pending_count = len(pending_tasks)

    return (
        "<!DOCTYPE html><html><head><meta charset=\"UTF-8\">"
        "<title>DAT Morning Brief — " + TODAY + "</title></head>"
        "<body style=\"background:#080c10;color:#e8edf5;font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:0;\">"
        "<div style=\"max-width:680px;margin:0 auto;padding:32px 24px;\">"
        "<div style=\"background:#0f1621;border:1px solid #1a2540;border-radius:12px;padding:24px;margin-bottom:24px;border-top:3px solid #00ff88;\">"
        "<div style=\"display:flex;align-items:center;gap:10px;margin-bottom:8px;\">"
        "<span style=\"font-size:24px;\">✈</span><div>"
        "<div style=\"font-size:18px;font-weight:800;color:#00ff88;\">District Award Travel</div>"
        "<div style=\"font-size:10px;color:#7a8ba0;font-family:monospace;letter-spacing:.1em;\">MORNING BRIEFING · " + NOW + "</div>"
        "</div></div>"
        "<div style=\"color:#7a8ba0;font-size:13px;margin-top:8px;\">Your engineers worked through the night. Here is what they built.</div>"
        "</div>"
        "<div style=\"display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;\">"
        "<div style=\"background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;\">"
        "<div style=\"font-size:26px;font-weight:700;color:#00ff88;font-family:monospace;\">" + str(total_completed) + "</div>"
        "<div style=\"font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;\">Tasks Built</div></div>"
        "<div style=\"background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;\">"
        "<div style=\"font-size:26px;font-weight:700;color:#00aaff;font-family:monospace;\">" + str(pending_count) + "</div>"
        "<div style=\"font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;\">In Queue</div></div>"
        "<div style=\"background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;\">"
        "<div style=\"font-size:26px;font-weight:700;color:#ffd700;font-family:monospace;\">3</div>"
        "<div style=\"font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;\">Engineers Active</div></div>"
        "</div>"
        "<div style=\"margin-bottom:8px;font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;\">── Tonight's Engineering Activity</div>"
        + eng_html +
        "<div style=\"margin-bottom:8px;margin-top:24px;font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;\">── Tomorrow Night at 1 AM</div>"
        + plan_html +
        "<div style=\"margin-top:32px;padding-top:16px;border-top:1px solid #1a2540;font-size:10px;color:#3d5068;font-family:monospace;text-align:center;\">"
        "District Award Travel · Autonomous Engineering System · Mitchell · Martin · Jeff"
        "</div></div></body></html>"
    )


def send_email(html_content):
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_user = os.environ.get("SMTP_USERNAME") or os.environ.get("REPORT_EMAIL")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    report_email = os.environ.get("REPORT_EMAIL")

    if not all([smtp_server, smtp_user, smtp_pass, report_email]):
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "DAT Morning Brief — " + TODAY
        msg["From"] = smtp_user
        msg["To"] = report_email
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_server, 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, report_email, msg.as_string())
        return True
    except Exception as e:
        print("Email failed: " + str(e))
        return False


def main():
    backlog = load_backlog()
    completions = get_todays_completions(backlog)
    pending_tasks = get_pending_tasks(backlog)

    html = build_html_report(backlog, completions, pending_tasks)

    brief_path = LOGS_DIR / ("morning_brief_" + TODAY + ".html")
    brief_path.write_text(html)
    print("Morning brief saved: " + str(brief_path))

    txt_lines = [
        "DISTRICT AWARD TRAVEL — MORNING BRIEF",
        "Date: " + TODAY + " · " + NOW,
        "=" * 50,
        "Tasks completed tonight: " + str(len(completions)),
        "Tasks still pending: " + str(len(pending_tasks)),
        "",
        "COMPLETED TASKS:",
    ]
    for t in completions:
        txt_lines.append("  [" + t.get("assigned_to", "?").upper() + "] " + t["id"] + ": " + t["title"])
        if t.get("completion_summary"):
            txt_lines.append("    -> " + t["completion_summary"])
    txt_lines.append("")
    txt_lines.append("PLANNED FOR TOMORROW NIGHT:")
    seen = set()
    for t in pending_tasks:
        eng = t.get("assigned_to", "?")
        if eng not in seen:
            txt_lines.append("  [" + eng.upper() + "] " + t["id"] + ": " + t["title"])
            seen.add(eng)

    txt_path = LOGS_DIR / ("morning_brief_" + TODAY + ".txt")
    txt_path.write_text("\n".join(txt_lines))

    if send_email(html):
        print("Morning brief emailed to " + os.environ.get("REPORT_EMAIL", ""))
    else:
        print("Email not configured — brief saved to logs/ only.")


if __name__ == "__main__":
    mai()
