import json
import datetime
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


def main():
    backlog = load_backlog()
    completions = get_todays_completions(backlog)
    pending_tasks = get_pending_tasks(backlog)

    engineer_info = {
        "mitchell": {"name": "Mitchell Hashimoto", "color": "#00ff88", "emoji": "🏗️"},
        "martin":   {"name": "Martin Thompson",    "color": "#00aaff", "emoji": "⚡"},
        "jeff":     {"name": "Jeff Dean",           "color": "#9b59ff", "emoji": "🧠"},
    }

    # Build engineer sections
    by_engineer = {"mitchell": [], "martin": [], "jeff": []}
    for t in completions:
        eng = t.get("assigned_to")
        if eng in by_engineer:
            by_engineer[eng].append(t)

    eng_html = ""
    for eng_id, tasks in by_engineer.items():
        info = engineer_info[eng_id]
        tasks_html = ""
        if tasks:
            for t in tasks:
                summary = t.get("completion_summary", "Task completed.")
                files = t.get("files_created", [])
                files_str = " · ".join([f.split("/")[-1] for f in files[:4]]) if files else ""
                tasks_html += (
                    "<div style='background:#0f1621;border-left:3px solid " + info["color"] + ";border-radius:6px;padding:12px 16px;margin-bottom:8px;border:1px solid #1a2540;'>"
                    "<div style='font-size:11px;color:#7a8ba0;font-family:monospace;'>" + t["id"] + " · " + t.get("priority","").upper() + "</div>"
                    "<div style='font-size:13px;color:#e8edf5;font-weight:600;margin:4px 0;'>" + t["title"] + "</div>"
                    "<div style='font-size:12px;color:#7a8ba0;'>" + summary + "</div>"
                    + ("<div style='font-size:10px;color:#3d5068;font-family:monospace;margin-top:4px;'>FILES: " + files_str + "</div>" if files_str else "") +
                    "</div>"
                )
        else:
            tasks_html = "<div style='font-size:12px;color:#3d5068;font-family:monospace;'>No tasks completed tonight.</div>"

        eng_html += (
            "<div style='margin-bottom:24px;'>"
            "<div style='font-size:13px;font-weight:700;color:" + info["color"] + ";margin-bottom:8px;'>"
            + info["emoji"] + " " + info["name"] + " — " + str(len(tasks)) + " task(s)</div>"
            + tasks_html + "</div>"
        )

    # Build tomorrow section
    plan_html = ""
    shown = set()
    for t in pending_tasks:
        eng_id = t.get("assigned_to")
        if eng_id in engineer_info and eng_id not in shown:
            info = engineer_info[eng_id]
            plan_html += (
                "<div style='background:#0f1621;border-left:3px solid " + info["color"] + ";border-radius:6px;padding:10px 14px;margin-bottom:6px;border:1px solid #1a2540;'>"
                "<div style='font-size:10px;color:#3d5068;font-family:monospace;'>" + info["name"].upper() + " · " + t.get("priority","").upper() + "</div>"
                "<div style='font-size:12px;color:#e8edf5;margin-top:2px;'>" + t["title"] + "</div>"
                "</div>"
            )
            shown.add(eng_id)

    if not plan_html:
        plan_html = "<div style='color:#3d5068;font-family:monospace;font-size:11px;'>Engineers will generate new tasks tonight.</div>"

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<title>DAT Morning Brief — " + TODAY + "</title></head>"
        "<body style='background:#080c10;color:#e8edf5;font-family:Segoe UI,sans-serif;margin:0;padding:0;'>"
        "<div style='max-width:680px;margin:0 auto;padding:32px 24px;'>"

        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:12px;padding:24px;margin-bottom:24px;border-top:3px solid #00ff88;'>"
        "<div style='font-size:22px;font-weight:800;color:#00ff88;'>✈ District Award Travel</div>"
        "<div style='font-size:11px;color:#7a8ba0;font-family:monospace;margin-top:4px;'>MORNING BRIEF · " + NOW + "</div>"
        "<div style='color:#7a8ba0;font-size:13px;margin-top:10px;'>Your engineers worked through the night. Here is what they built.</div>"
        "</div>"

        "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px;'>"
        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;font-weight:700;color:#00ff88;font-family:monospace;'>" + str(len(completions)) + "</div>"
        "<div style='font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;'>Tasks Built</div></div>"
        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;font-weight:700;color:#00aaff;font-family:monospace;'>" + str(len(pending_tasks)) + "</div>"
        "<div style='font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;'>In Queue</div></div>"
        "<div style='background:#0f1621;border:1px solid #1a2540;border-radius:8px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;font-weight:700;color:#ffd700;font-family:monospace;'>3</div>"
        "<div style='font-size:9px;color:#3d5068;font-family:monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:2px;'>Engineers</div></div>"
        "</div>"

        "<div style='font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;margin-bottom:12px;'>── Tonight's Work</div>"
        + eng_html +

        "<div style='font-size:9px;color:#00ff88;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;margin-bottom:12px;margin-top:24px;'>── Tomorrow Night at 1 AM</div>"
        + plan_html +

        "<div style='margin-top:32px;padding-top:16px;border-top:1px solid #1a2540;font-size:10px;color:#3d5068;font-family:monospace;text-align:center;'>"
        "District Award Travel · Autonomous Engineering System · Mitchell · Martin · Jeff"
        "</div></div></body></html>"
    )

    brief_path = LOGS_DIR / ("morning_brief_" + TODAY + ".html")
    brief_path.write_text(html)
    print("Morning brief saved: " + str(brief_path))

    # Print summary to Actions log
    print("")
    print("=" * 50)
    print("DISTRICT AWARD TRAVEL — " + TODAY)
    print("Tasks built tonight: " + str(len(completions)))
    print("Tasks in queue: " + str(len(pending_tasks)))
    print("")
    for t in completions:
        print("  [DONE] " + t.get("assigned_to","?").upper() + " — " + t["title"])
    print("=" * 50)


if __name__ == "__main__":
    main()
