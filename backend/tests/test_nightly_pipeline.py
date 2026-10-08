import os
import pytest
from datetime import datetime, timedelta
import agent
import database
from run_nightly import run_nightly_pipeline

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_nightly_dashboard.db")

@pytest.fixture(autouse=True)
def setup_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    database.init_db()

    temp_vault = tmp_path / "obsidian_vault"
    (temp_vault / "Daily_Briefs").mkdir(parents=True, exist_ok=True)
    (temp_vault / "04_Archives").mkdir(parents=True, exist_ok=True)
    (temp_vault / "02_Areas" / "Fitness").mkdir(parents=True, exist_ok=True)

    # Seed workout routine
    workout_md = temp_vault / "02_Areas" / "Fitness" / "Workout_Routine.md"
    workout_md.write_text("""# Workout Regimen
### Monday
- Squat 3x5
- Bench Press 3x5
### Tuesday
- Deadlift 1x5
- Overhead Press 3x5
### Wednesday
- Rest Day
### Thursday
- Squat 3x5
- Incline Press 3x8
### Friday
- Barbell Row 3x8
- Pull-ups 3x10
### Saturday
- Cardio 30 mins
### Sunday
- Mobility & Stretch
""", encoding="utf-8")

    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    import run_nightly
    monkeypatch.setattr(run_nightly, "generate_daily_brief", agent.generate_daily_brief)
    monkeypatch.setattr(run_nightly, "generate_daily_summary", agent.generate_daily_summary)
    monkeypatch.setattr(run_nightly, "archive_and_reset_tasks_nightly", agent.archive_and_reset_tasks_nightly)

    yield temp_vault

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


def test_generate_daily_summary_and_brief_cleanup(setup_isolation):
    temp_vault = setup_isolation
    today = "2026-10-05"

    conn = database.get_db_connection()
    c = conn.cursor()

    # 1. Seed events
    c.execute("""
        INSERT INTO calendar_events (title, description, start_time, end_time, source)
        VALUES (?, ?, ?, ?, ?)
    """, ("Design Sync", "Review UI architecture", f"{today} 10:00:00", f"{today} 11:00:00", "google"))

    # 2. Seed completed task & pending task
    c.execute("""
        INSERT INTO tasks (title, category, status, completed_at, recurrence)
        VALUES (?, ?, ?, ?, ?)
    """, ("Deploy API", "dev", "completed", f"{today} 15:30:00", "none"))
    c.execute("""
        INSERT INTO tasks (title, category, status, due_date, recurrence)
        VALUES (?, ?, ?, ?, ?)
    """, ("Refactor Tests", "dev", "pending", today, "none"))

    # 3. Seed transactions
    c.execute("""
        INSERT INTO transactions (date, amount, type, category, merchant, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today, 12.50, "expense", "food", "Chipotle", "Lunch burrito"))
    c.execute("""
        INSERT INTO transactions (date, amount, type, category, merchant, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today, 250.00, "income", "freelance", "Client A", "Consulting"))

    # 4. Seed health vitals
    c.execute("""
        INSERT INTO health_logs (date, weight_lbs, sleep_hours, mood, systolic, diastolic)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today, 180.5, 7.5, "8/10", 120, 80))

    conn.commit()
    conn.close()

    # Pre-create a daily brief for today
    brief_path = os.path.join(str(temp_vault), "Daily_Briefs", f"Daily_Brief_{today}.md")
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write("# Daily Brief - Today")

    assert os.path.exists(brief_path)

    # Execute daily summary
    agent.generate_daily_summary(target_date=today)

    # 1. Verify archive created with exact requested sections
    archive_path = os.path.join(str(temp_vault), "04_Archives", f"Daily_Summary_{today}.md")
    assert os.path.exists(archive_path)

    with open(archive_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert f"# Daily Summary — {today}" in content
    assert "## 📅 Events" in content
    assert "Design Sync" in content
    assert "## ✅ Completed Tasks (1)" in content
    assert "Deploy API" in content
    # Pending task should NOT be in the completed tasks section
    assert "Refactor Tests" not in content
    assert "## 💰 Transactions" in content
    assert "Chipotle" in content
    assert "$12.50" in content
    assert "$250.00" in content
    assert "Total spent:" in content
    assert "Total income:" in content
    assert "## ❤️ Vitals & Health" in content
    assert "180.5 lbs" in content
    assert "7.5 hours" in content
    assert "120/80" in content

    # 2. Verify active daily brief for today was deleted
    assert not os.path.exists(brief_path)


def test_archive_and_reset_tasks_nightly(setup_isolation):
    conn = database.get_db_connection()
    c = conn.cursor()

    # 1. Completed one-off task
    c.execute("INSERT INTO tasks (title, status, recurrence) VALUES (?, ?, ?)", ("One-off task", "completed", "none"))
    oneoff_id = c.lastrowid
    c.execute("INSERT INTO task_subtasks (task_id, title, is_completed) VALUES (?, ?, ?)", (oneoff_id, "Sub 1", 1))

    # 2. Pending one-off task
    c.execute("INSERT INTO tasks (title, status, recurrence) VALUES (?, ?, ?)", ("Pending task", "pending", "none"))
    pending_id = c.lastrowid

    # 3. Completed daily recurring task
    c.execute("INSERT INTO tasks (title, status, recurrence, completed_at) VALUES (?, ?, ?, ?)",
              ("Daily workout", "completed", "daily", "2026-10-05 08:00:00"))
    daily_id = c.lastrowid
    c.execute("INSERT INTO task_subtasks (task_id, title, is_completed) VALUES (?, ?, ?)", (daily_id, "Stretch", 1))

    conn.commit()
    conn.close()

    # Run GC and reset
    agent.archive_and_reset_tasks_nightly(target_date="2026-10-05")

    conn = database.get_db_connection()
    c = conn.cursor()

    # One-off completed task should be deleted
    c.execute("SELECT * FROM tasks WHERE id = ?", (oneoff_id,))
    assert c.fetchone() is None
    # Orphaned subtasks should be deleted
    c.execute("SELECT * FROM task_subtasks WHERE task_id = ?", (oneoff_id,))
    assert c.fetchone() is None

    # Pending task should remain untouched
    c.execute("SELECT * FROM tasks WHERE id = ?", (pending_id,))
    assert c.fetchone() is not None

    # Daily recurring task should be reset to pending, completed_at cleared, subtask unchecked
    c.execute("SELECT * FROM tasks WHERE id = ?", (daily_id,))
    daily_task = c.fetchone()
    assert daily_task is not None
    assert daily_task["status"] == "pending"
    assert daily_task["completed_at"] is None

    c.execute("SELECT * FROM task_subtasks WHERE task_id = ?", (daily_id,))
    sub = c.fetchone()
    assert sub is not None
    assert sub["is_completed"] == 0

    conn.close()


def test_generate_daily_brief_tomorrow(setup_isolation):
    temp_vault = setup_isolation
    tomorrow = "2026-10-06"  # Tuesday

    conn = database.get_db_connection()
    c = conn.cursor()

    # Event tomorrow
    c.execute("""
        INSERT INTO calendar_events (title, description, start_time, end_time, source)
        VALUES (?, ?, ?, ?, ?)
    """, ("Dentist Appointment", "Checkup", f"{tomorrow} 14:00:00", f"{tomorrow} 15:00:00", "local_ics"))

    # Tasks due tomorrow, overdue, upcoming
    c.execute("INSERT INTO tasks (title, status, due_date, category) VALUES (?, ?, ?, ?)",
              ("Submit Quarterly Taxes", "pending", tomorrow, "finance"))
    c.execute("INSERT INTO tasks (title, status, due_date, category) VALUES (?, ?, ?, ?)",
              ("Renew Passport", "pending", "2026-10-01", "personal"))
    c.execute("INSERT INTO tasks (title, status, due_date, category) VALUES (?, ?, ?, ?)",
              ("Read Documentation", "pending", "2026-10-10", "learning"))

    conn.commit()
    conn.close()

    agent.generate_daily_brief(target_date=tomorrow)

    brief_path = os.path.join(str(temp_vault), "Daily_Briefs", f"Daily_Brief_{tomorrow}.md")
    assert os.path.exists(brief_path)

    with open(brief_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert f"# Daily Brief — {tomorrow}" in content
    assert "## 📅 Schedule" in content
    assert "Dentist Appointment" in content
    assert "## 🎯 Tasks Due Today (1)" in content
    assert "Submit Quarterly Taxes" in content
    assert "## ⚠️ Overdue / Pushed Off (1)" in content
    assert "Renew Passport" in content
    assert "## 📋 Coming Up Next" in content
    assert "Read Documentation" in content
    assert "## 🏋️ Workout Routine" in content
    assert "Deadlift 1x5" in content


def test_end_to_end_nightly_pipeline(setup_isolation):
    temp_vault = setup_isolation
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Pre-seed today's brief
    today_brief = os.path.join(str(temp_vault), "Daily_Briefs", f"Daily_Brief_{today}.md")
    with open(today_brief, "w", encoding="utf-8") as f:
        f.write("# Brief for today")

    # Run full nightly pipeline
    run_nightly_pipeline()

    # Verify:
    # 1. Today's brief is gone
    assert not os.path.exists(today_brief)
    # 2. Today's archive exists
    today_archive = os.path.join(str(temp_vault), "04_Archives", f"Daily_Summary_{today}.md")
    assert os.path.exists(today_archive)
    # 3. Tomorrow's brief exists
    tomorrow_brief = os.path.join(str(temp_vault), "Daily_Briefs", f"Daily_Brief_{tomorrow}.md")
    assert os.path.exists(tomorrow_brief)
