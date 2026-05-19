import os
import sys
import json
import datetime
import re
from pathlib import Path
from groq import Groq

BASE_DIR = Path(__file__).parent.parent
TASKS_FILE = BASE_DIR / "tasks" / "backlog.json"
AGENTS_DIR = BASE_DIR / "agents"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def load_backlog():
    with open(TASKS_FILE) as f:
        return json.load(f)


def save_backlog(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_pending_tasks(backlog, engineer_id):
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    task_list = backlog.get("backlog") or backlog.get("tasks") or []
    tasks = [
        t for t in task_list
        if t.get("assigned_to") == engineer_id and t.get("status") == "pending"
    ]
    return sorted(tasks, key=lambda t: order.get(t.get("priority", "low"), 9))


def build_prompt(engineer_id, task, persona_text, backlog):
    today = datetime.date.today().isoformat()
    lines = [
        persona_text,
        "",
        "---",
        "## TONIGHT'S ASSIGNMENT — " + today,
        "",
        "You are running inside GitHub Actions on Ubuntu.",
        "Project root: " + str(BASE_DIR),
        "",
        "Your assigned task:",
        "```json",
        json.dumps(task, indent=2),
        "```",
        "",
        "## INSTRUCTIONS",
        "",
        "1. Write every file needed to complete this task.",
        "2. Before each file write this line exactly: FILE: path/to/file.py",
        "   Then open a code block, write the full file, close the code block.",
        "3. Every file must be 100% working code. No TODOs. No placeholders.",
        "4. After writing files, update tasks/backlog.json:",
        '   Set this task status to "completed"',
        '   Add completed_at: ' + today,
        '   Add completion_summary: 2-3 sentences describing what you built.',
        "",
        "Start writing files now.",
    ]
    return "\n".join(lines)


def write_file(filepath, content):
    if not filepath.startswith("/"):
        full_path = BASE_DIR / filepath
    else:
        full_path = Path(filepath)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print("  Wrote: " + str(full_path))


def parse_and_write_files(response_text, engineer_id):
    pattern = re.finditer(
        r'FILE:\s*([^\n]+)\n```[^\n]*\n(.*?)```',
        response_text, re.DOTALL
    )
    files_written = []
    for match in pattern:
        filepath = match.group(1).strip()
        content = match.group(2)
        write_file(filepath, content)
        files_written.append(filepath)

    if files_written:
        print("[" + engineer_id + "] Wrote " + str(len(files_written)) + " file(s).")
    else:
        print("[" + engineer_id + "] Warning: no FILE: blocks found in response.")

    try:
        backlog = load_backlog()
        today = datetime.date.today().isoformat()
        for t in backlog["backlog"]:
            if t["assigned_to"] == engineer_id and t["status"] == "pending":
                t["status"] = "completed"
                t["completed_at"] = today
                t["completion_summary"] = "Completed by " + engineer_id + " on " + today + "."
                break
        save_backlog(backlog)
    except Exception as e:
        print("[" + engineer_id + "] Could not update backlog: " + str(e))


def run(engineer_id):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set.")
        sys.exit(1)

    persona_file = AGENTS_DIR / ("engineer_" + engineer_id + ".md")
    if not persona_file.exists():
        print("ERROR: Missing persona file: " + str(persona_file))
        sys.exit(1)

    backlog = load_backlog()
    tasks = get_pending_tasks(backlog, engineer_id)

    if not tasks:
        print("[" + engineer_id + "] No pending tasks.")
        return

    task = tasks[0]
    print("[" + engineer_id + "] Task: " + task["id"] + " — " + task["title"])

    persona_text = persona_file.read_text()
    prompt = build_prompt(engineer_id, task, persona_text, backlog)

    client = Groq(api_key=api_key)
    print("[" + engineer_id + "] Calling Groq...")

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are " + engineer_id + ", an autonomous software engineer. "
                    "Write complete working code. "
                    "Always prefix each file with: FILE: path/to/file "
                    "followed by a code block. Never write partial code."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=8000,
        stream=True,
    )

    response_text = ""
    for chunk in completion:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        response_text += delta

    print("\n[" + engineer_id + "] Done.")
    parse_and_write_files(response_text, engineer_id)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("marcus", "jordan", "priya"):
        print("Usage: python agents/run_engineer.py <marcus|jordan|priya>")
        sys.exit(1)
    run(sys.argv[1])
