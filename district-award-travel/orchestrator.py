"""
District Award Travel — Autonomous Engineering Orchestrator
Runs nightly, deploys 3 AI engineers to build the platform.
Each engineer reads the task backlog, picks their tasks, and commits real code.

Usage:
  python orchestrator.py                  # Run all engineers
  python orchestrator.py --engineer marcus # Run one engineer only
  python orchestrator.py --dry-run         # Preview tasks without executing
"""

import os
import sys
import json
import subprocess
import argparse
import datetime
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
TASKS_FILE = BASE_DIR / "tasks" / "backlog.json"
AGENTS_DIR = BASE_DIR / "agents"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ENGINEERS = {
    "marcus": {
        "persona_file": AGENTS_DIR / "engineer_marcus.md",
        "color": "\033[92m",  # green
    },
    "jordan": {
        "persona_file": AGENTS_DIR / "engineer_jordan.md",
        "color": "\033[94m",  # blue
    },
    "priya": {
        "persona_file": AGENTS_DIR / "engineer_priya.md",
        "color": "\033[95m",  # purple
    },
}

RESET = "\033[0m"
BOLD = "\033[1m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"


def log(msg, color="", end="\n"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {msg}{RESET}", end=end)


def load_backlog():
    with open(TASKS_FILE) as f:
        return json.load(f)


def save_backlog(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_pending_tasks(backlog, engineer_id):
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks = [
        t for t in backlog["backlog"]
        if t["assigned_to"] == engineer_id and t["status"] == "pending"
    ]
    tasks.sort(key=lambda t: priority_order.get(t["priority"], 99))
    return tasks


def build_engineer_prompt(engineer_id, task, persona_text, backlog_json):
    return f"""
{persona_text}

---
## TONIGHT'S ASSIGNMENT

You have been invoked as part of the District Award Travel nightly engineering run.
The date is {datetime.date.today().isoformat()}.
The project root is at: {BASE_DIR}

Your assigned task:

```json
{json.dumps(task, indent=2)}
```

Full backlog context:
```json
{json.dumps(backlog_json, indent=2)}
```

## INSTRUCTIONS

1. Complete this task in full. Write every file listed in the acceptance criteria.
2. All files go in the paths specified in the task description, relative to: {BASE_DIR}
3. Create any directories that don't exist.
4. When done, update tasks/backlog.json:
   - Change this task's status from "pending" to "completed"
   - Add a "completed_at" field with today's date
   - Add a "completion_summary" field with 2-3 sentences describing exactly what you built
5. Write a log file to: {LOGS_DIR / f"{engineer_id}_{datetime.date.today().isoformat()}.log"}
   Format: timestamp | task_id | action | result

Begin now. Write real, working code. No placeholders.
""".strip()


def check_claude_cli():
    """Verify claude CLI is available."""
    result = subprocess.run(
        ["claude", "--version"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def run_engineer(engineer_id, task, dry_run=False):
    """Invoke Claude Code CLI as an autonomous engineer."""
    color = ENGINEERS[engineer_id]["color"]
    persona_file = ENGINEERS[engineer_id]["persona_file"]

    log(f"  Engineer {engineer_id.upper()} → Task {task['id']}: {task['title']}", color)

    if dry_run:
        log(f"  [DRY RUN] Would execute task {task['id']}", YELLOW)
        return True

    persona_text = persona_file.read_text()
    backlog = load_backlog()
    prompt = build_engineer_prompt(engineer_id, task, persona_text, backlog)

    # Save prompt to a temp file for the claude CLI
    prompt_file = BASE_DIR / f".tmp_prompt_{engineer_id}.txt"
    prompt_file.write_text(prompt)

    try:
        log(f"  Invoking Claude Code for {engineer_id}...", color)

        result = subprocess.run(
            [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "-p", prompt
            ],
            cwd=str(BASE_DIR),
            capture_output=False,
            text=True,
            timeout=600,  # 10 min per task
        )

        if result.returncode == 0:
            log(f"  ✓ {engineer_id} completed task {task['id']}", color)
            return True
        else:
            log(f"  ✗ {engineer_id} task {task['id']} exited with code {result.returncode}", RED)
            return False

    except subprocess.TimeoutExpired:
        log(f"  ✗ {engineer_id} timed out on task {task['id']} (>10 min)", RED)
        return False
    except FileNotFoundError:
        log(f"  ✗ 'claude' CLI not found. Is Claude Code installed?", RED)
        log(f"    Install: npm install -g @anthropic-ai/claude-code", YELLOW)
        return False
    finally:
        if prompt_file.exists():
            prompt_file.unlink()


def git_commit_all(summary_lines):
    """Commit all new/modified files to git."""
    try:
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True, capture_output=True)
        date_str = datetime.date.today().isoformat()
        commit_msg = f"[{date_str}] Nightly engineering run\n\n" + "\n".join(summary_lines)
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=BASE_DIR, check=True, capture_output=True
        )
        log("Git commit successful.", "\033[92m")

        # Push if remote is configured
        result = subprocess.run(
            ["git", "remote"], cwd=BASE_DIR, capture_output=True, text=True
        )
        if "origin" in result.stdout:
            subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, capture_output=True)
            log("Pushed to GitHub.", "\033[92m")
    except subprocess.CalledProcessError as e:
        log(f"Git operation failed: {e}", RED)


def write_morning_brief(results):
    """Write a morning briefing summary to logs."""
    date_str = datetime.date.today().isoformat()
    brief_path = LOGS_DIR / f"morning_brief_{date_str}.txt"

    lines = [
        "=" * 60,
        f"DISTRICT AWARD TRAVEL — MORNING BRIEF",
        f"Date: {date_str}",
        f"Generated: {datetime.datetime.now().strftime('%H:%M:%S UTC')}",
        "=" * 60,
        "",
        "ENGINEERING ACTIVITY:",
    ]

    for eng_id, tasks in results.items():
        lines.append(f"\n  {eng_id.upper()} ({ENGINEERS[eng_id]['persona_file'].stem.replace('engineer_', '').title()}):")
        if tasks:
            for t in tasks:
                lines.append(f"    ✓ {t['id']}: {t['title']}")
        else:
            lines.append("    — No pending tasks")

    lines += [
        "",
        "Check tasks/backlog.json for detailed completion summaries.",
        "Check logs/ for per-engineer execution logs.",
        "=" * 60,
    ]

    brief_path.write_text("\n".join(lines))
    log(f"\nMorning brief saved: {brief_path}", CYAN)
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="District Award Travel — Nightly Orchestrator")
    parser.add_argument("--engineer", choices=list(ENGINEERS.keys()), help="Run a single engineer only")
    parser.add_argument("--dry-run", action="store_true", help="Show tasks without executing")
    parser.add_argument("--task", help="Run a specific task ID only")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}")
    print("╔══════════════════════════════════════════════╗")
    print("║   DISTRICT AWARD TRAVEL                      ║")
    print("║   Autonomous Engineering Orchestrator v1.0   ║")
    print(f"║   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}               ║")
    print("╚══════════════════════════════════════════════╝")
    print(RESET)

    backlog = load_backlog()
    engineers_to_run = [args.engineer] if args.engineer else list(ENGINEERS.keys())
    results = {e: [] for e in engineers_to_run}

    for engineer_id in engineers_to_run:
        color = ENGINEERS[engineer_id]["color"]
        tasks = get_pending_tasks(backlog, engineer_id)

        if args.task:
            tasks = [t for t in tasks if t["id"] == args.task]

        log(f"\nEngineer: {engineer_id.upper()} — {len(tasks)} pending task(s)", color + BOLD)

        for task in tasks:
            success = run_engineer(engineer_id, task, dry_run=args.dry_run)
            if success:
                results[engineer_id].append(task)
            # Reload backlog after each task (engineer may have updated it)
            backlog = load_backlog()

    if not args.dry_run:
        summary_lines = [
            f"{eng}: {len(tasks)} task(s) completed"
            for eng, tasks in results.items()
            if tasks
        ]
        if summary_lines:
            git_commit_all(summary_lines)

    write_morning_brief(results)


if __name__ == "__main__":
    main()
