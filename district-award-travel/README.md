# District Award Travel — Autonomous Engineering System

Three AI engineers build your platform every night while you sleep.

## Engineers

| Engineer | Role | Builds |
|---|---|---|
| **Marcus Webb** | Lead Backend & API Engineer | Database, FastAPI server, award scrapers, morning reports |
| **Jordan Reyes** | Automation & Browser Engineer | ANA/BA/AC portal automation, transfer bonus monitoring, seat holds |
| **Priya Kapoor** | Frontend & Platform Engineer | Business dashboard, client management, booking pipeline UI |

## First-Time Setup (Run Once)

```
python setup.py
```

This installs all dependencies, sets up your `.env`, initializes git, and schedules the nightly run.

## Running the Engineers

```bash
# Run all 3 engineers tonight (picks up all pending tasks)
python orchestrator.py

# Run one engineer only
python orchestrator.py --engineer marcus

# Preview what tasks are pending without executing
python orchestrator.py --dry-run
```

## Adding Work for the Engineers

Edit `tasks/backlog.json` — add a new task object to the `"backlog"` array:

```json
{
  "id": "TASK-009",
  "title": "What you want built",
  "assigned_to": "marcus",
  "priority": "high",
  "status": "pending",
  "description": "Detailed description of what to build and where to save it.",
  "acceptance_criteria": ["List", "of", "requirements"],
  "tech": ["Python", "FastAPI"],
  "estimated_hours": 3
}
```

Assign to: `marcus`, `jordan`, or `priya`

## Morning Briefing

After each nightly run, find your summary at:
```
logs/morning_brief_YYYY-MM-DD.txt
```

## Safety

- `BOOKING_ENABLED=false` by default — agents **cannot book** unless you explicitly set this to `true` in `.env`
- All credentials stored locally in `.env` — never committed to git
- Every agent action is logged to `logs/`

## Project Structure

```
district-award-travel/
├── orchestrator.py          ← Nightly run engine
├── setup.py                 ← One-time setup wizard
├── tasks/
│   ├── backlog.json         ← Task queue for all engineers
│   ├── results/             ← Scraped award data output
│   ├── transfer_bonuses.json← Live transfer bonus database
│   └── alerts.json          ← New opportunities discovered
├── agents/
│   ├── engineer_marcus.md   ← Marcus's persona + instructions
│   ├── engineer_jordan.md   ← Jordan's persona + instructions
│   └── engineer_priya.md   ← Priya's persona + instructions
├── platform/
│   ├── src/
│   │   ├── models/          ← Database models (Marcus)
│   │   ├── api/             ← FastAPI backend (Marcus)
│   │   ├── scrapers/        ← Award scrapers (Marcus)
│   │   ├── automation/      ← Browser automation (Jordan)
│   │   └── reports/         ← Morning report (Marcus)
│   └── public/              ← Dashboard UI (Priya)
├── logs/                    ← All agent logs + morning briefs
├── requirements.txt
├── package.json
└── .env                     ← Your credentials (never committed)
```
