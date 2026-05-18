# How to Launch District Award Travel
## Zero installs. Browser only. 15 minutes.

---

## STEP 1 — Create Your GitHub Repository (3 min)

1. Open **github.com** in your browser
2. Click the **+** in the top right → **New repository**
3. Name it: `district-award-travel`
4. Set to **Private**
5. Leave everything else unchecked
6. Click **Create repository**

---

## STEP 2 — Upload Your Code to GitHub (5 min)

1. On your new empty GitHub repo page, click **uploading an existing file**
2. Open File Explorer on your computer and navigate to:
   ```
   C:\Users\BRADEN_SALCETTI\district-award-travel
   ```
3. Select ALL files and folders → drag them into the GitHub upload box
4. Scroll down, click **Commit changes**

Your code is now on GitHub.

---

## STEP 3 — Get Your Anthropic API Key (2 min)

This is what powers Marcus, Jordan, and Priya. Without it they can't write code.

1. Go to **console.anthropic.com**
2. Sign in (or create a free account)
3. Click **API Keys** in the left sidebar
4. Click **Create Key** → name it `district-award-travel`
5. Copy the key (starts with `sk-ant-...`)
6. **Save it somewhere safe — you only see it once**

> Cost: The engineers use ~$0.50–$2.00 per nightly run using Claude Opus.
> New accounts get $5 free credits — enough for several nights of work.

---

## STEP 4 — Add Your API Key to GitHub Secrets (3 min)

GitHub Secrets keep your credentials safe. Engineers read them automatically.

1. Go to your GitHub repo → **Settings** tab
2. In the left sidebar → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these one by one:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your `sk-ant-...` key from Step 3 |
| `REPORT_EMAIL` | Your email address (for morning briefings) |

Optional (add later for email reports):
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PASSWORD` | Your Gmail app password |

---

## STEP 5 — Trigger Your First Engineering Run (1 min)

1. Go to your GitHub repo → **Actions** tab
2. Click **Nightly Engineering Run — District Award Travel** in the left list
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch Marcus, Jordan, and Priya start working in real time

You'll see three jobs running in parallel. Each one shows live logs of what the engineer is writing.

---

## From Here — You're Hands Off

**Every night at 2:00 AM** GitHub automatically wakes up your engineers.
They check the task backlog, write code, and commit it to your repo.

**To see what they built:** Go to your GitHub repo → click on any file they modified.

**To assign new work:** Go to `tasks/backlog.json` on GitHub → click the pencil (edit) icon → add a task → commit.

**To view the morning brief:** Go to `logs/` folder in your repo → open `morning_brief_YYYY-MM-DD.html`

---

## Company Roster

Open `company/roster.html` in your browser any time to see your full team of 16.

---

## Questions?

Everything runs on GitHub's free servers. You pay only for Anthropic API usage
(the AI brain of your engineers). Estimated: $1–3/night for a full 3-engineer run.
