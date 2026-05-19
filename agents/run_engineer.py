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

You are running inside GitHub Actions on an Ubuntu server.
The project root is: {BASE_DIR}

Your assigned task:
```json
{json.dumps(task, indent=2)}
