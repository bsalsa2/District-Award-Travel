"""
District Award Travel - Nightly Engineer Runner
Runs for up to 1 hour per engineer, completing as many tasks as possible.
Primary AI: DeepSeek. Fallback: Gemini.
"""

import os
import sys
import json
import datetime
import re
import time
from pathlib import Path
from openai import OpenAI
import google.generativeai as genai

BASE_DIR = Path(__file__).parent.parent
TASKS_FILE = BASE_DIR / "tasks" / "backlog.json"
AGENTS_DIR = BASE_DIR / "agents"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MAX_RUNTIME_SECONDS = 3600


def load_backlog():
    with open(TASKS_FILE) as f:
        return json.load(f)


def save_backlog(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_pending_tasks(backlog, engineer_id):
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    task_list = backlog.get("backlog") or []
    tasks = [
        t for t in task_list
        if t.get("assigned_to") == engineer_id and t.get("status") == "pending"
    ]
    return sorted(tasks, key=lambda t: order.get(t.get("priority", "low"), 9))


def build_prompt(engineer_id, task, persona_text):
    today = datetime.date.today().isoformat()
    lines = [
        persona_text,
        "",
        "---",
        "## TONIGHT'S TASK — " + today,
        "",
        "Project root: " + str(BASE_DIR),
        "",
        "Your assigned task:",
        "```json",
        json.dumps(task, indent=2),
        "```",
        "",
        "## INSTRUCTIONS",
        "",
        "Write every file needed to complete this task.",
        "Before each file write exactly: FILE: path/to/file.py",
        "Then open a code block, write the complete file, close it.",
        "Every file must be 100% working code. No TODOs. No placeholders.",
        "Be creative and build something genuinely useful for an award travel business.",
        "",
        "After all files, update tasks/backlog.json:",
        "  - Set this task status to completed",
        "  - Add completed_at: " + today,
        "  - Add completion_summary: exactly what you built in 2-3 sentences",
        "",
        "Also add 2 NEW tasks to the backlog for tomorrow night based on what you just built.",
        "Assign them to yourself (" + engineer_id + "), set status to pending.",
        "",
        "Start writing now.",
    ]
    return "\n".join(lines)


def call_deepseek(prompt, engineer_id):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    print("[" + engineer_id + "] Calling DeepSeek...")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are " + engineer_id + ", an elite autonomous software engineer "
                    "at District Award Travel. Write complete, production-quality code. "
                    "Always prefix each file with FILE: path/to/file followed by a code block. "
                    "Never write partial implementations or TODOs. "
                    "Be creative — build tools that genuinely help an award travel business."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=8000,
        stream=True,
    )

    result = ""
    for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        result += delta
    print()
    return result


def call_gemini(prompt, engineer_id):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    print("[" + engineer_id + "] Falling back to Gemini...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=(
            "You are " + engineer_id + ", an elite autonomous software engineer "
            "at District Award Travel. Write complete working code. "
            "Always prefix each file with FILE: path/to/file followed by a code block. "
            "Never write partial code or TODOs."
        )
    )
    response = model.generate_content(prompt)
    print(response.text)
    return response.text


def call_ai(prompt, engineer_id):
    try:
        return call_deepseek(prompt, engineer_id)
    except Exception as e:
        print("[" + engineer_id + "] DeepSeek failed (" + str(e) + ") — switching to Gemini")
        return call_gemini(prompt, engineer_id)


def write_file(filepath, content):
    if not filepath.startswith("/"):
        full_path = BASE_DIR / filepath
    else:
        full_path = Path(filepath)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print("  Wrote: " + str(full_path))
    return str(full_path)


def parse_and_write_files(response_text, engineer_id):
    pattern = re.finditer(
        r'FILE:\s*([^\n]+)\n```[^\n]*\n(.*?)```',
        response_text, re.DOTALL
    )
    files_written = []
    for match in pattern:
        filepath = match.group(1).strip()
        content = match.group(2)
        written = write_file(filepath, content)
        files_written.append(written)

    if files_written:
        print("[" + engineer_id + "] Wrote " + str(l
