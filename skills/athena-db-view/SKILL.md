---
name: athena-db-view
description: View and query the Athena OS SQLite database tables.
platforms: [linux]
---

# Athena DB View Skill

This skill allows you to inspect and query the SQLite database (`life_dashboard.db`) of the Athena OS dashboard.

## Database Tables

The database contains the following tables:
- **`accounts`**: Financial accounts (Checking, Savings, Credit Card, Investment, Cash)
- **`budgets`**: Category budget limits (e.g., limits for food, utilities)
- **`recurring_transactions`**: Recurring bills, subscriptions, and pay schedules
- **`transactions`**: Financial ledger entries (income and expenses)
- **`fitness_logs`**: Workouts, activities, distance, intensity, and calories burned
- **`health_logs`**: Daily vitals (weight, sleep, mood, blood pressure, hydration, stress, energy)
- **`meal_logs`**: Nutritional tracking (meal type, calories, protein, carbs, fat)
- **`mindfulness_logs`**: Meditation, focus, and breathing sessions
- **`learning_progress`**: Study topics, category, hours spent, status, and source links
- **`job_applications`**: Job applications tracking (company, role, status, salary range)
- **`habit_logs`**: Daily habits completion checklist (e.g., "Code 1 Hour", "Workout")
- **`tasks`**: Tasks database synchronized with the Obsidian vault
- **`calendar_events`**: Calendar schedules (Google & local ICS)
- **`processed_files`**: Logs of files processed through the inbox

## Usage

Use the command-line utility `backend/db_cli.py` inside the project root ``.

### 1. List Tables

Check all available tables in the database:
```bash
python backend/db_cli.py list-tables
```

### 2. Show Table Contents

Display the latest rows in a table (defaults to 20 rows, ordered by date or ID descending). 
Format is a Markdown table by default:
```bash
python backend/db_cli.py show <table_name> [--limit <number>]
```

For raw JSON output (preferred for structured parsing by agents):
```bash
python backend/db_cli.py show <table_name> --json [--limit <number>]
```

*Example (Markdown table):*
```bash
python backend/db_cli.py show transactions --limit 5
```

*Example (Raw JSON):*
```bash
python backend/db_cli.py show health_logs --limit 3 --json
```

### 3. Run Custom SQL Query

Run any custom `SELECT` statement:
```bash
python backend/db_cli.py query "SELECT category, SUM(amount) FROM transactions WHERE type='expense' GROUP BY category"
```

To run a query and output JSON:
```bash
python backend/db_cli.py query "SELECT * FROM budgets" --json
```

## Related Skills

- `athena-db-edit` — Insert, update, or delete rows in the database.
- `athena-nightly` — Ingest database changes and daily summaries.
- `obsidian` — Manage markdown notes and tasks in the vault.
