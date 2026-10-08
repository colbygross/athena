# ATHENA Remote Access Guide (MacBook Pro <-> Linux)

This guide documents how to access, query, and automate **Athena OS** from your MacBook Pro over Tailscale. It contains connection parameters, CLI commands, agent instructions, and Ollama inference offloading steps.

---

## 🌐 Network & Host Configuration

| Property | Value |
| :--- | :--- |
| **Athena Host (Linux)** | `archer-xps-15-9510` |
| **Athena Tailscale IP** | `100.78.213.125` |
| **Athena Host User** | `archer` |
| **Athena Repository Path** | `/home/archer/ATHENA` |
| **Python Virtualenv** | `/home/archer/ATHENA/.venv/bin/python` |
| **Web / API Port** | `http://100.78.213.125:8000` |
| **MacBook Pro** | `colbys-macbook-pro` (`100.108.154.118`) |

---

## ⚡ 1. Fast Verification (From Your Mac)

Open Terminal on your Mac and verify connectivity:

```bash
# Ping Athena over Tailscale
ping -c 3 100.78.213.125

# Connect via Tailscale SSH (no keys needed if Tailscale SSH is enabled)
tailscale ssh archer@100.78.213.125
# or standard SSH:
ssh archer@100.78.213.125
```

> [!NOTE]
> If Tailscale SSH is not enabled yet on the Linux host, run `sudo tailscale up --ssh` on the Athena machine once.

---

## 🤖 2. Agent System Prompt / Skill Snippet

Copy and paste this section into your Mac agent's system prompt, `.cursorrules`, `CLAUDE.md`, or custom instructions:

```markdown
### Remote ATHENA OS Access
You have access to the user's Athena OS personal telemetry and knowledge engine running on `archer@100.78.213.125` via Tailscale SSH.

When the user asks questions about their personal data (finances, habits, health, fitness, career, learning, tasks, calendar), execute commands remotely via SSH:

1. Base SSH command format:
   ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py <COMMAND>"

2. Query telemetry in JSON or formatted tables:
   - List tables: `... db_cli.py list-tables`
   - Show recent records: `... db_cli.py show <table_name> --limit 10 [--json]`
   - Run custom SQL: `... db_cli.py query "<SQL_QUERY>" [--json]`

3. Inspect Obsidian knowledge vault notes:
   - Search notes: `ssh archer@100.78.213.125 "grep -ri '<term>' /home/archer/ATHENA/obsidian_vault/"`
   - Read specific note: `ssh archer@100.78.213.125 "cat /home/archer/ATHENA/obsidian_vault/<path>.md"`
   - View active tasks: `ssh archer@100.78.213.125 "cat /home/archer/ATHENA/obsidian_vault/tasks.md"`

Always present queried numbers accurately and cleanly. Never execute destructive drop or delete commands without confirmation.
```

---

## 🛠️ 3. Command Cheat Sheet (Run From Your Mac)

All commands can be executed remotely from your Mac terminal or by your local Mac agent:

### A. Database CLI (`backend/db_cli.py`)

#### View Recent Telemetry
```bash
# 1. Recent expenses & income
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py show transactions --limit 10"

# 2. Vitals & biometric logs (last 7 days)
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py show health_logs --limit 7"

# 3. Workouts & fitness logs
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py show fitness_logs --limit 5"

# 4. Job applications kanban status
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py show job_applications"

# 5. Habit completion streaks
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py show habit_logs --limit 10"
```

#### Run Arbitrary SQL (Read-Only or Aggregations)
```bash
# Monthly spending grouped by category
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py query \"SELECT category, SUM(amount) as total FROM transactions WHERE type='expense' GROUP BY category ORDER BY total DESC\""

# Today's meals and macros
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py query \"SELECT meal_type, description, calories, protein_g, carbs_g, fat_g FROM meal_logs WHERE date = date('now')\""

# Get output as JSON for programmatic processing
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py query \"SELECT * FROM accounts\" --json"
```

#### Insert New Telemetry Record
```bash
# Insert a new health log
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/db_cli.py insert health_logs '{\"date\":\"2026-09-16\",\"weight_lbs\":175.2,\"sleep_hours\":7.5,\"mood\":\"focused\",\"energy_level\":8,\"stress_level\":3}'"
```

---

### B. Obsidian Knowledge Base Management

The Obsidian vault is located at `/home/archer/ATHENA/obsidian_vault`.

```bash
# Read today's brief
ssh archer@100.78.213.125 "cat /home/archer/ATHENA/obsidian_vault/Daily_Briefs/Daily_Brief_\$(date +%Y-%m-%d).md 2>/dev/null || ls -t /home/archer/ATHENA/obsidian_vault/Daily_Briefs/ | head -1"

# Read Financial Summary
ssh archer@100.78.213.125 "cat /home/archer/ATHENA/obsidian_vault/Summaries/Financial_Summary.md"

# Drop a note into the Inbox for automated processing
ssh archer@100.78.213.125 "echo -e '# Meeting Notes\nDiscussion about project milestones...' > /home/archer/ATHENA/obsidian_vault/Inbox/meeting_note.md"

# Run Athena Mind cross-link optimizer
ssh archer@100.78.213.125 "cd /home/archer/ATHENA && .venv/bin/python backend/athena_mind.py find-links --fix"
```

---

## 🌐 4. Web Dashboard & REST API

If the Athena server is running (`./launch_dashboard.sh` or Docker):

- **Live Web Dashboard:** [http://100.78.213.125:8000](http://100.78.213.125:8000) (Open directly in Safari / Chrome on Mac)
- **Interactive Swagger Docs:** [http://100.78.213.125:8000/docs](http://100.78.213.125:8000/docs)
- **OpenAPI Schema (for MCP/Agents):** [http://100.78.213.125:8000/openapi.json](http://100.78.213.125:8000/openapi.json)

---

## 🧠 5. Reverse Link: Using Mac's Powerful LLMs for Athena

You can have Athena send its background document extraction, vision parsing, and daily briefing tasks over Tailscale to your MacBook Pro.

### On your MacBook Pro:
Allow Ollama to listen across Tailscale:
```bash
# If running Ollama in a terminal:
OLLAMA_HOST="0.0.0.0:11434" ollama serve

# Or for the macOS menu bar app:
launchctl setenv OLLAMA_HOST "0.0.0.0:11434"
# Then restart Ollama from the menu bar
```

### On the Athena machine (`.env`):
Update `/home/archer/ATHENA/.env`:
```env
LLM_ENABLED=true
OLLAMA_BASE_URL=http://100.108.154.118:11434
OLLAMA_MODEL=qwen2.5:32b
OLLAMA_VISION_MODEL=qwen2.5-vl:7b
OLLAMA_FINANCE_MODEL=qwen2.5-coder:14b
```

---

## 📦 6. How to Drop This File to Your Mac (Taildrop)

From this machine's terminal, send this guide directly to your MacBook Pro via Taildrop:

```bash
tailscale file cp /home/archer/ATHENA/ATHENA_MAC_ACCESS.md colbys-macbook-pro:
```

Once received on your Mac, it will appear in your Mac's **Downloads** folder or in the Tailscale menu bar tray.
