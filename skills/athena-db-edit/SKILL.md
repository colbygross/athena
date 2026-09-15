---
name: athena-db-edit
description: Add, update, and delete entries in the Athena OS SQLite database.
platforms: [linux]
---

# Athena DB Edit Skill

This skill allows you to insert new records, update existing ones, or delete entries from the Athena OS database using the CLI tool `backend/db_cli.py`.

## Usage

All commands should be executed from the project root ``. Data mappings must be provided in valid JSON format.

### 1. Add (Insert) Row

Insert a new record into a table:
```bash
python backend/db_cli.py add <table_name> '<json_data>'
```

*Examples:*

**Add a financial transaction (income or expense):**
```bash
python backend/db_cli.py add transactions '{"date": "2026-05-23", "amount": 15.50, "type": "expense", "category": "food", "merchant": "Cafe", "description": "Lunch with colleague", "account_id": 1}'
```

**Add a financial transfer transaction (moves money between accounts):**
```bash
python backend/db_cli.py add transactions '{"date": "2026-05-23", "amount": 120.00, "type": "transfer", "category": "transfer", "merchant": "Internal Transfer", "description": "Transfer from Cash to Checking", "account_id": 5, "transfer_account_id": 9}'
```
⚠️ Transfers require `type: "transfer"`, `category: "transfer"`, `account_id` (source account) and `transfer_account_id` (destination account). They do not impact monthly income or expense totals.

**Add health/vitals log (note: use weight_lbs in pounds, not weight_kg):**
```bash
python backend/db_cli.py add health_logs '{"date": "2026-05-23", "weight_lbs": 173.1, "sleep_hours": 7.5, "mood": "Energetic", "systolic": 120, "diastolic": 80, "water_ml": 1500, "energy_level": 8, "stress_level": 3}'
```

**Add a meal log:**
```bash
python backend/db_cli.py add meal_logs '{"date": "2026-05-23", "meal_type": "lunch", "description": "Grilled Chicken Salad with avocado", "calories": 480, "protein_g": 38.0, "carbs_g": 12.0, "fat_g": 14.5}'
```

**Add a mindfulness log:**
```bash
python backend/db_cli.py add mindfulness_logs '{"date": "2026-05-23", "activity_type": "Meditation", "duration_minutes": 15, "notes": "Breath focus, felt relaxed"}'
```

**Add a learning progress entry:**
```bash
python backend/db_cli.py add learning_progress '{"date": "2026-05-23", "topic": "SQLite PRAGMA statements", "category": "Computer Science", "hours_spent": 1.5, "notes": "Learned about foreign key constraints and schema introspection in SQLite.", "status": "completed"}'
```

**Add a calendar event (updates calendar.ics automatically):**
```bash
python backend/db_cli.py add calendar_events '{"title": "PWS Orientation", "description": "Location: Nantasket Beach", "start_time": "2026-06-03 14:30:00", "end_time": "2026-06-03 18:30:00", "source": "local_ics"}'
```
⚠️ `source` must be `'google'` or `'local_ics'` (CHECK constraint). Do NOT use `'manual'`.
⚠️ Calling `db_cli.py` to add, update, or delete in `calendar_events` automatically serializes the database events to `obsidian_vault/calendar.ics` and keeps them synced in real-time. The unique `event_uid` is generated automatically as `UUID@local` if not provided.

**Add a task (will sync to tasks.md and vault notes):**
```bash
python backend/db_cli.py add tasks '{"title": "Review linear algebra", "category": "learning", "status": "pending", "due_date": "2026-06-05", "priority": "high", "importance": "major"}'
```
⚠️ Tasks added to the database are synchronized with `obsidian_vault/tasks.md` and markdown checklists in the vault. Custom columns `priority` (`'low'`, `'medium'`, `'high'`) and `importance` (`'major'`, `'minor'`) are supported.

## Pitfalls

- **CHECK constraints will reject invalid values.** If you get `CHECK constraint failed`, inspect the table schema to find the constrained column (e.g. `type` in transactions must be `'income'`, `'expense'`, or `'transfer'`).
- **`mood` is TEXT in health_logs** — pass a string like `"6"`, not an integer.
- **health_logs uses `weight_lbs` in pounds** — do not use `weight_kg` or it will reject the schema or store incorrect values.
- **health_logs shorthand format:** Archer often sends compact data like `"weight69 sleep6 mood6 water 1000, energy7 stress 7"`. Parse it as: weight_lbs (numeric), sleep_hours (numeric), mood (string), water_ml (numeric), energy_level (numeric), stress_level (numeric). Use today's date if no date is specified.

### 2. Update Row

Update specific columns of an existing row by its unique integer `id`:
```bash
python backend/db_cli.py update <table_name> <id> '<json_data>'
```

*Examples:*

**Change a job application status:**
```bash
python backend/db_cli.py update job_applications 3 '{"status": "interviewing", "notes": "First round panel interview scheduled for Monday at 10 AM."}'
```

**Update water intake and stress levels for a date in health logs:**
```bash
python backend/db_cli.py update health_logs 5 '{"water_ml": 2250, "stress_level": 2}'
```

### 3. Delete Row

Delete a row from a table by its unique `id`:
```bash
python backend/db_cli.py delete <table_name> <id>
```

*Example:*
Remove a redundant task:
```bash
python backend/db_cli.py delete tasks 12
```

## Related Skills

- `athena-db-view` — Query and show database tables.
- `athena-nightly` — Ingest database changes and daily summaries.
- `obsidian` — Manage markdown notes and tasks in the vault.
