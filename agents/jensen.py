"""
Jensen Huang - Nightly Idea Generator
Runs before the engineers. Reads what's been built, generates bold new tasks.
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


def get_next_task_id(backlog):
    """Return the next available task ID, always higher than any existing ID."""
    task_list = backlog.get("backlog", [])
    max_num = 999
    for t in task_list:
        tid = t.get("id", "")
        if tid.startswith("TASK-"):
            try:
                num = int(tid.split("-")[1])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return max_num + 1


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


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    print("Falling back to Gemini...")
    from google import genai as google_genai
    from google.genai import types as genai_types
    client = google_genai.Client(api_key=api_key)
    system = (
        "You are Jensen Huang, CEO of NVIDIA. You think in accelerated computing, "
        "AI platforms, and systems that scale to millions of users. "
        "You are advising District Award Travel — an award flight consulting business "
        "that uses AI to find and book the best award flight redemptions for clients. "
        "Generate bold, creative, technically ambitious tasks for the engineering team."
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7,
            max_output_tokens=4000,
        ),
    )
    return response.text


def call_ai(prompt):
    errors = []
    try:
        return call_groq(prompt)
    except Exception as e:
        errors.append("Groq: " + str(e))
        print("Groq failed — trying Gemini")
    try:
        return call_gemini(prompt)
    except Exception as e:
        errors.append("Gemini: " + str(e))
        print("Gemini failed — trying Mistral")
    try:
        return call_mistral(prompt)
    except Exception as e:
        errors.append("Mistral: " + str(e))
    raise Exception("All Jensen AI APIs failed:\n" + "\n".join(errors))


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
    next_id = get_next_task_id(backlog)

    id_examples = (
        "TASK-" + str(next_id) + ", TASK-" + str(next_id + 1) + ", TASK-" + str(next_id + 2) +
        ", TASK-" + str(next_id + 3) + ", TASK-" + str(next_id + 4) + ", TASK-" + str(next_id + 5)
    )

    prompt = (
        "Date: " + TODAY + "\n\n"
        "Here is what the District Award Travel engineering team has built recently:\n"
        + completed_summary + "\n\n"
        "There are currently " + str(pending_count) + " pending tasks in the backlog.\n\n"
        "Generate 6 new ambitious tasks — 2 for each engineer:\n"
        "- mitchell: infrastructure, DevOps, monitoring, automation (files go in platform/infra/)\n"
        "- martin: backend APIs, data pipelines, FastAPI endpoints, SQLite (files go in platform/src/)\n"
        "- jeff: AI/ML models, frontend dashboard, HTML/JS tools (files go in platform/src/ or platform/public/)\n\n"
        "District Award Travel is an award flight consulting business. Clients pay to have experts "
        "find and book award flights using airline miles/points. Make tasks that build REAL, USEFUL software "
        "for this business — tools that actually help find award availability, value points, manage clients, "
        "track redemptions, monitor award space, and present data in dashboards.\n\n"
        "IMPORTANT: Use these exact sequential IDs (do not reuse old IDs): " + id_examples + "\n\n"
        "Return ONLY a JSON array:\n"
        "```json\n"
        "[\n"
        "  {\n"
        "    \"id\": \"TASK-" + str(next_id) + "\",\n"
        "    \"title\": \"Short descriptive title\",\n"
        "    \"assigned_to\": \"mitchell\",\n"
        "    \"priority\": \"high\",\n"
        "    \"status\": \"pending\",\n"
        "    \"description\": \"Detailed description of exactly what to build and what files to create.\"\n"
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
