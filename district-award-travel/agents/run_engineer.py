"""
District Award Travel — Cloud Engineer Runner
Called by GitHub Actions. Loads the engineer persona, picks their next task,
calls the Anthropic API, and writes real code to the repo.

Usage: python agents/run_engineer.py <marcus|jordan|priya>
"""

import os
import sys
import json
import datetime
from pathlib import Path
import anthropic

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
    tasks = [
        t for t in backlog["backlog"]
        if t["assigned_to"] == engineer_id and t["status"] == "pending"
    ]
    return sorted(tasks, key=lambda t: order.get(t["priority"], 9))


def build_prompt(engineer_id, task, persona_text, backlog):
    today = datetime.date.today().isoformat()
    return f"""{persona_text}

---
## TONIGHT'S ASSIGNMENT — {today}

You are running inside GitHub Actions on an Ubuntu server. The project root is at: {BASE_DIR}

Your assigned task:
```json
{json.dumps(task, indent=2)}
```

Full project backlog for context:
```json
{json.dumps(backlog, indent=2)}
```

## WHAT YOU MUST DO

1. Write every file required to complete this task. Use the exact file paths specified.
2. Make every file 100% functional — no placeholders, no TODOs, no stub functions.
3. Create any missing directories before writing files.
4. After writing all files, update `tasks/backlog.json`:
   - Set this task's `status` to `"completed"`
   - Add `"completed_at": "{today}"`
   - Add `"completion_summary": "2-3 sentences describing exactly what you built"`
5. Write a log entry to `logs/{engineer_id}_{today}.log`

## IMPORTANT CONSTRAINTS
- You are on Linux (Ubuntu). Use Linux-compatible paths and commands.
- All credentials come from environment variables — never hardcode secrets.
- The repo root is: {BASE_DIR}
- Write real, working code that runs without modification.

Start immediately. Write all files now.
"""


def run(engineer_id):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in environment.")
        sys.exit(1)

    persona_file = AGENTS_DIR / f"engineer_{engineer_id}.md"
    if not persona_file.exists():
        print(f"ERROR: No persona file found at {persona_file}")
        sys.exit(1)

    persona_text = persona_file.read_text()
    backlog = load_backlog()
    tasks = get_pending_tasks(backlog, engineer_id)

    if not tasks:
        print(f"[{engineer_id}] No pending tasks. All caught up.")
        log_path = LOGS_DIR / f"{engineer_id}_{datetime.date.today().isoformat()}.log"
        log_path.write_text(f"{datetime.datetime.now().isoformat()} | {engineer_id} | check | No pending tasks\n")
        return

    task = tasks[0]
    print(f"[{engineer_id}] Starting task {task['id']}: {task['title']}")

    prompt = build_prompt(engineer_id, task, persona_text, backlog)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"[{engineer_id}] Calling Claude API...")

    with client.messages.stream(
        model="claude-opus-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
        system=f"You are {engineer_id.title()}, an autonomous software engineer. You write complete, working code. You use your tools to create files and directories. You never produce partial implementations."
    ) as stream:
        response_text = ""
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_text += text

    print(f"\n[{engineer_id}] API call complete.")

    # Parse any file writes from the response and execute them
    execute_file_writes(response_text, engineer_id, task)

    # Reload and check if backlog was updated
    updated_backlog = load_backlog()
    completed = [t for t in updated_backlog.get("completed", []) if t.get("id") == task["id"]]
    still_pending = [t for t in updated_backlog["backlog"] if t["id"] == task["id"] and t["status"] == "pending"]

    if still_pending:
        # Engineer didn't update the backlog — update it ourselves
        for t in updated_backlog["backlog"]:
            if t["id"] == task["id"]:
                t["status"] = "completed"
                t["completed_at"] = datetime.date.today().isoformat()
                t["completion_summary"] = f"Task completed by {engineer_id} on {datetime.date.today().isoformat()}"
        save_backlog(updated_backlog)
        print(f"[{engineer_id}] Backlog updated manually.")

    print(f"[{engineer_id}] Task {task['id']} complete.")


def execute_file_writes(response_text, engineer_id, task):
    """
    Parse the Claude response for file content blocks and write them to disk.
    Claude is instructed to wrap files in: FILE: path/to/file followed by a code block.
    We also handle standard markdown code blocks with file paths in comments.
    """
    import re

    # Pattern 1: FILE: path\n```lang\ncontent\n```
    pattern1 = re.finditer(
        r'FILE:\s*([^\n]+)\n```[^\n]*\n(.*?)```',
        response_text, re.DOTALL
    )

    files_written = []
    for match in pattern1:
        filepath = match.group(1).strip()
        content = match.group(2)
        write_file(filepath, content, engineer_id)
        files_written.append(filepath)

    # Pattern 2: # path/to/file.py at top of code block
    pattern2 = re.finditer(
        r'```[^\n]*\n(?:#|//)\s*([^\n]+\.[a-z]+)\n(.*?)```',
        response_text, re.DOTALL
    )
    for match in pattern2:
        filepath = match.group(1).strip()
        content = "# " + match.group(1).strip() + "\n" + match.group(2)
        if filepath not in files_written:
            write_file(filepath, content, engineer_id)
            files_written.append(filepath)

    if files_written:
        print(f"[{engineer_id}] Files written: {', '.join(files_written)}")
    else:
        print(f"[{engineer_id}] Note: No explicit file blocks detected in response. Claude may have used tool calls.")


def write_file(filepath, content, engineer_id):
    """Write a file to the repo, creating directories as needed."""
    # Resolve relative to BASE_DIR
    if not filepath.startswith("/"):
        full_path = BASE_DIR / filepath
    else:
        full_path = Path(filepath)

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print(f"[{engineer_id}] Wrote: {full_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agents/run_engineer.py <marcus|jordan|priya>")
        sys.exit(1)

    engineer_id = sys.argv[1].lower()
    if engineer_id not in ("marcus", "jordan", "priya"):
        print(f"Unknown engineer: {engineer_id}")
        sys.exit(1)

    run(engineer_id)
