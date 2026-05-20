"""
Jensen Huang - Nightly Idea Generator
Runs at 9 PM EST (2 AM UTC) — before the engineers start at 8 PM and 3 AM.
Reads what's been built, generates bold new tasks for tomorrow.
"""

import os
import json
import datetime
from pathlib import Path
from openai import OpenAI

BASE_DIR = Path(__file__).parent.parent
TASKS_FILE = BASE_DIR / "tasks" / "backlog.json"

TODAY = datetime.date.today().isoformat()


def load_backlog():
    with open(TASKS_FILE) as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"backlog": data, "completed": []}
    if "backlog" not in data:
        data["backlog"] = []
    return data


def save_backlog(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_completed_summary(backlog):
    completed = [t for t in backlog.get("backlog", []) if t.get("status") == "completed"]
    lines = []
    for t in completed[-10:]:
        lines.append("- " + t.get("title", "") + " (" + t.get("assigned_to", "") + ")")
    return "\n".join(lines) if lines else "Nothing completed yet."


def get_pending_count(backlog):
    return len([t for t in backlog.get("backlog", []) if t.get("status") == "pending"])


def call_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Jensen Huang, CEO of NVIDIA. You think in accelerated computing, "
                    "AI platforms, and systems that scale to millions of users. "
                    "You are advising District Award Travel — an award flight consulting business "
                    "that uses AI to find and book the best award flight redemptions for clients. "
                    "Generate bold, creative, technically ambitious tasks for the engineering team."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=4000,
    )
    return response.choices[0].message.content


def call_mistral(prompt):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set")
    client = OpenAI(api_key=api_key, base_url="https://api.mistral.ai/v1")
    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Jensen Huang, CEO of NVIDIA. You think in accelerated computing, "
                    "AI platforms, and systems that scale to millions of users. "
                    "You are advising District Award Travel — an award flight consulting business. "
                    "Generate bold, creative, technically ambitious tasks for the engineering team."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=4000,
    )
    return response.choices[0].message.content


def call_ai(prompt):
    try:
        return call_groq(prompt)
    except Exception as e:
        print("Groq failed (" + str(e) + ") — trying Mistral")
        return call_mistral(prompt)


def parse_tasks(response_text):
    import re
    match = re.search(r'```json\s*(\[.*?\])\s*```', response_text, re.DOTALL)
    if not match:
        return []
    try:
        tasks = json.loads(match.group(1))
        if isinstance(tasks, list):
            return [t for t in tasks if isinstance(t, dict)]
    except Exception:
        pass
    return []


def main():
    backlog = load_backlog()
    completed_summary = get_completed_summary(backlog)
    pending_count = get_pending_count(backlog)

    prompt = (
        "Date: " + TODAY + "\n\n"
        "Here is what the District Award Travel engineering team has built recently:\n"
        + completed_summary + "\n\n"
        "There are currently " + str(pending_count) + " pending tasks in the backlog.\n\n"
        "Generate 6 new ambitious tasks — 2 for each engineer:\n"
        "- mitchell: infrastructure, DevOps, monitoring, automation\n"
        "- martin: backend APIs, data pipelines, search systems, performance\n"
        "- jeff: AI/ML models, frontend dashboard, intelligence tools\n\n"
        "Think BIG. What would make District Award Travel the most powerful award travel platform on the internet?\n\n"
        "Return ONLY a JSON array like this:\n"
        "```json\n"
        "[\n"
        "  {\n"
        "    \"id\": \"TASK-" + str(200 + int(datetime.datetime.now().timestamp()) % 100) + "\",\n"
        "    \"title\": \"...\",\n"
        "    \"assigned_to\": \"mitchell\",\n"
        "    \"priority\": \"high\",\n"
        "    \"status\": \"pending\",\n"
        "    \"description\": \"...\"\n"
        "  }\n"
        "]\n"
        "```"
    )

    print("Jensen Huang generating tasks for " + TODAY + "...")

    try:
        response = call_ai(prompt)
        print(response)
        new_tasks = parse_tasks(response)

        if new_tasks:
            task_list = backlog.get("backlog", [])
            existing_ids = {t.get("id") for t in task_list if isinstance(t, dict)}
            added = 0
            for t in new_tasks:
                if t.get("id") not in existing_ids:
                    task_list.append(t)
                    existing_ids.add(t.get("id"))
                    added += 1
            backlog["backlog"] = task_list
            save_backlog(backlog)
            print("Jensen added " + str(added) + " new tasks to the backlog.")
        else:
            print("No tasks parsed from response.")

    except Exception as e:
        print("Jensen failed: " + str(e))


if __name__ == "__main__":
    main()
