---
name: athena-context-lookup
description: Translate a user question about themselves into targeted database queries and vault lookups. The primary decision-making skill for "what do I know about X?" questions.
platforms: [linux]
---

# Athena Context Lookup Skill

This is the **routing skill** — the first skill to apply when a user asks a self-referential question. It maps topics to the right data sources (DB table, vault directory, or summary file) so the agent fetches only what is relevant.

Use this skill before `athena-db-view` or `athena-vault-search` to decide *where* to look.

---

## Topic → Data Source Map

| Topic / Question Type | Primary Source | Secondary Source |
|---|---|---|
| Money, spending, budget, income | `transactions`, `accounts`, `budgets` tables | `Summaries/Financial_Summary.md` |
| Subscriptions, recurring bills | `recurring_transactions` table | — |
| Workouts, exercise, fitness | `fitness_logs` table | `02_Areas/Fitness/` notes |
| Weight, sleep, mood, vitals, blood pressure | `health_logs` table | `02_Areas/Health/` notes |
| Food, meals, calories, macros, nutrition | `meal_logs` table | — |
| Meditation, mindfulness, breathing | `mindfulness_logs` table | — |
| Studying, learning, topics, hours spent | `learning_progress` table | `02_Areas/Learning/` + `Summaries/Learning_Career_Summary.md` |
| Jobs, applications, companies, interviews | `job_applications` table | `02_Areas/Career/` notes |
| Habits, streaks, daily checklist | `habit_logs` table | `tasks.md` |
| Tasks, to-dos, due dates | `tasks` table | `tasks.md`, `Daily_Briefs/` |
| Calendar, schedule, events | `calendar_events` table | `calendar.ics` |
| Processed files, uploaded docs | `processed_files` table | `storage/` directory |
| Projects (active) | `01_Projects/` vault notes | — |
| Daily overview / briefing | `Daily_Briefs/Daily_Brief_YYYY-MM-DD.md` | All summary files |

---

## Lookup Playbook

### "How am I doing with money / finances?"
```bash
# 1. Recent transactions
python backend/db_cli.py show transactions --limit 10

# 2. Spending by category
python backend/db_cli.py query "SELECT category, SUM(amount) as total FROM transactions WHERE type='expense' GROUP BY category ORDER BY total DESC"

# 3. Budget vs. actual
python backend/db_cli.py query "SELECT b.category, b.limit_amount, COALESCE(SUM(t.amount),0) as spent FROM budgets b LEFT JOIN transactions t ON b.category=t.category AND t.type='expense' GROUP BY b.category"

# 4. Account balances
python backend/db_cli.py show accounts
```

---

### "How has my health/fitness been?"
```bash
# 1. Last 7 days of vitals
python backend/db_cli.py show health_logs --limit 7

# 2. Recent workouts
python backend/db_cli.py show fitness_logs --limit 5

# 3. Meal logs today
python backend/db_cli.py query "SELECT * FROM meal_logs WHERE date = date('now') ORDER BY id DESC"

# 4. Hydration / energy / stress trends
python backend/db_cli.py query "SELECT date, water_ml, energy_level, stress_level FROM health_logs ORDER BY date DESC LIMIT 7"
```

---

### "What am I learning / studying?"
```bash
# 1. Recent study sessions
python backend/db_cli.py show learning_progress --limit 10

# 2. Hours by topic/category this week
python backend/db_cli.py query "SELECT topic, category, SUM(hours_spent) as total_hours FROM learning_progress WHERE date >= date('now', '-7 days') GROUP BY topic"

# 3. In-progress topics
python backend/db_cli.py query "SELECT * FROM learning_progress WHERE status='in-progress'"

# 4. Vault companion notes
find obsidian_vault/02_Areas/Learning -name "*.md" | xargs ls -lt 2>/dev/null | head -10
```

---

### "What are my job applications / career status?"
```bash
# 1. All job applications
python backend/db_cli.py show job_applications

# 2. Active applications only
python backend/db_cli.py query "SELECT company, role, status, date_applied, notes FROM job_applications WHERE status NOT IN ('rejected','withdrawn') ORDER BY date_applied DESC"

# 3. Find companion notes for a company
grep -ri "<company_name>" obsidian_vault --include="*.md" -l
```

---

### "What are my tasks / what do I have to do?"
```bash
# 1. All pending tasks
python backend/db_cli.py query "SELECT title, category, priority, importance, due_date FROM tasks WHERE status='pending' ORDER BY due_date ASC, priority DESC"

# 2. Overdue tasks
python backend/db_cli.py query "SELECT title, category, due_date FROM tasks WHERE status='pending' AND due_date < date('now') ORDER BY due_date ASC"

# 3. Tasks due today
python backend/db_cli.py query "SELECT title, category, priority FROM tasks WHERE status='pending' AND due_date = date('now')"

# 4. High-importance pending tasks
python backend/db_cli.py query "SELECT title, due_date FROM tasks WHERE status='pending' AND importance='major' ORDER BY due_date ASC"

# 5. Task breakdown by category
python backend/db_cli.py query "SELECT category, COUNT(*) as count FROM tasks WHERE status='pending' GROUP BY category"
```

---

### "What's on my schedule / calendar?"
```bash
# 1. Upcoming events
python backend/db_cli.py query "SELECT title, description, start_time, end_time FROM calendar_events WHERE start_time >= datetime('now') ORDER BY start_time ASC LIMIT 10"

# 2. Events this week
python backend/db_cli.py query "SELECT title, start_time FROM calendar_events WHERE start_time BETWEEN datetime('now') AND datetime('now', '+7 days') ORDER BY start_time ASC"
```

---

### "What habits have I been tracking?"
```bash
# 1. Habit completion for today
python backend/db_cli.py query "SELECT habit_name, completed, notes FROM habit_logs WHERE date = date('now')"

# 2. Completion rate last 7 days
python backend/db_cli.py query "SELECT habit_name, SUM(completed) as days_completed, COUNT(*) as days_tracked FROM habit_logs WHERE date >= date('now', '-7 days') GROUP BY habit_name"

# 3. Streak per habit (consecutive days completed)
python backend/db_cli.py query "SELECT habit_name, completed, date FROM habit_logs ORDER BY habit_name, date DESC LIMIT 30"
```

---

### "What files/documents have I processed?"
```bash
# 1. All processed files
python backend/db_cli.py show processed_files --limit 20

# 2. By category
python backend/db_cli.py query "SELECT category, COUNT(*) as count FROM processed_files GROUP BY category"

# 3. Find a specific document
python backend/db_cli.py query "SELECT * FROM processed_files WHERE original_name LIKE '%<keyword>%'"
```

---

### "Tell me about [topic/project]"
1. First search the vault for the topic:
```bash
grep -ri "<topic>" obsidian_vault --include="*.md" -l
find obsidian_vault -name "*.md" | grep -i "<topic>"
```
2. Read the matching notes with `cat`
3. Check if it links to a storage file (`meta_storage_relative_path`) → use `athena-file-retrieve`
4. Cross-reference DB for structured data related to the topic

---

## JSON Output for Agent Parsing

Append `--json` to any `db_cli.py show` or `db_cli.py query` command to get structured JSON instead of a Markdown table. This is preferred when the agent is parsing results programmatically:
```bash
python backend/db_cli.py show transactions --json --limit 5
python backend/db_cli.py query "SELECT * FROM tasks WHERE status='pending'" --json
```

---

## Related Skills

- `athena-vault-search` — Filename, tag, and full-text search of vault notes.
- `athena-file-retrieve` — Read the original source file behind a companion note.
- `athena-db-view` — Raw table inspection and custom SQL queries.
- `athena-db-edit` — Log new data discovered or inferred from the conversation.
