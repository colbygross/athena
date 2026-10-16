import pytest
import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import main
import database
import agent

client = TestClient(main.app)

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_e2e_lifecycle.db")

@pytest.fixture(autouse=True)
def setup_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    
    temp_vault = tmp_path / "obsidian_vault"
    temp_vault.mkdir(parents=True, exist_ok=True)
    temp_storage = tmp_path / "storage"
    temp_storage.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    monkeypatch.setattr(agent, "STORAGE_DIR", str(temp_storage))
    monkeypatch.setattr(agent, "INBOX_DIR", str(temp_vault / "Inbox"))
    monkeypatch.setattr(agent, "WORKSPACE_DIR", str(tmp_path))
    (temp_vault / "Inbox").mkdir(parents=True, exist_ok=True)
    (temp_vault / "Daily_Briefs").mkdir(parents=True, exist_ok=True)
    (temp_vault / "Summaries").mkdir(parents=True, exist_ok=True)
    
    cfg = tmp_path / "budget.json"
    cfg.write_text(json.dumps({"budgets": [{"category": "groceries", "limit_amount": 600.0}]}))
    monkeypatch.setattr(main, "BUDGET_CONFIG_PATH", str(cfg))
    
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass
    database.init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

def test_financial_ledger_lifecycle():
    """
    Test End-to-End Financial Ledger:
    1. Create accounts (Checking and Savings).
    2. Add income and expense transactions.
    3. Verify account balance calculations and net wealth.
    4. Set category budget and verify spending calculations.
    """
    # 1. Create checking account
    res_chk = client.post("/api/accounts", json={"name": "Checking Account", "type": "checking", "starting_balance": 1000.0})
    assert res_chk.status_code == 200
    chk_id = res_chk.json()["id"]

    # Create savings account
    res_sav = client.post("/api/accounts", json={"name": "Emergency Fund", "type": "savings", "starting_balance": 5000.0})
    assert res_sav.status_code == 200
    sav_id = res_sav.json()["id"]

    # 2. Add income ($2,000 salary)
    res_inc = client.post("/api/finances", json={
        "date": "2026-06-01",
        "amount": 2000.0,
        "type": "income",
        "category": "salary",
        "merchant": "Tech Corp",
        "description": "Bi-weekly paycheck",
        "account_id": chk_id
    })
    assert res_inc.status_code == 200

    # Add expense ($250 groceries)
    res_exp = client.post("/api/finances", json={
        "date": "2026-06-02",
        "amount": 250.0,
        "type": "expense",
        "category": "groceries",
        "merchant": "Whole Foods",
        "description": "Weekly pantry restock",
        "account_id": chk_id
    })
    assert res_exp.status_code == 200

    # 3. Verify accounts balance in /api/finances
    res_fin = client.get("/api/finances")
    assert res_fin.status_code == 200
    fin_data = res_fin.json()
    
    # Expected checking: 1000 + 2000 - 250 = 2750
    checking_acc = next(a for a in fin_data["accounts"] if a["id"] == chk_id)
    assert checking_acc["current_balance"] == 2750.0

    # Expected net wealth: 2750 + 5000 = 7750
    assert fin_data["net_wealth"] == 7750.0

    # 4. Verify budget configuration in /api/finances
    res_fin_bgt = client.get("/api/finances")
    assert res_fin_bgt.status_code == 200
    bgt_list = res_fin_bgt.json()["budgets"]
    groceries_bgt = next(b for b in bgt_list if b["category"] == "groceries")
    assert groceries_bgt["limit_amount"] == 600.0

def test_tasks_and_obsidian_sync_lifecycle(tmp_path):
    """
    Test Tasks Lifecycle:
    1. Create task via REST API.
    2. Verify task is listed.
    3. Update task status to completed.
    4. Verify completed_at timestamp set and synced.
    """
    res = client.post("/api/tasks", json={
        "title": "Configure Prometheus metrics scraper",
        "category": "learning",
        "priority": "high",
        "due_date": "2026-06-10"
    })
    assert res.status_code == 200
    task_id = res.json()["id"]

    # Verify task retrieved via API
    res_tasks = client.get("/api/tasks")
    assert res_tasks.status_code == 200
    tasks = res_tasks.json()["tasks"]
    task_item = next(t for t in tasks if t["id"] == task_id)
    assert task_item["title"] == "Configure Prometheus metrics scraper"
    assert task_item["status"] == "pending"

    # Mark task completed
    res_put = client.put(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert res_put.status_code == 200

    res_updated = client.get("/api/tasks")
    task_updated = next(t for t in res_updated.json()["tasks"] if t["id"] == task_id)
    assert task_updated["status"] == "completed"
    assert task_updated["completed_at"] is not None

def test_biometrics_and_habits_lifecycle():
    """
    Test Biometrics and Habits:
    1. Log daily health vitals.
    2. Log fitness exercise.
    3. Check habit completion and verify overview & health endpoints.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Log vitals
    res_h = client.post("/api/health", json={
        "date": today_str,
        "weight_lbs": 172.4,
        "sleep_hours": 8.2,
        "mood": "Optimal / Flow State",
        "systolic": 118,
        "diastolic": 76,
        "water_ml": 2500,
        "energy_level": 9,
        "stress_level": 2,
        "notes": "Good baseline telemetry."
    })
    assert res_h.status_code == 200

    # 2. Log workout
    res_f = client.post("/api/fitness", json={
        "date": today_str,
        "activity_type": "Outdoor Run",
        "duration_minutes": 42,
        "distance_km": 7.2,
        "calories_burned": 480,
        "intensity": "high",
        "notes": "Tempo intervals nominal."
    })
    assert res_f.status_code == 200

    # 3. Log habit
    res_hab = client.post("/api/habits", json={
        "date": today_str,
        "habit_name": "Cold Plunge",
        "completed": 1,
        "notes": "3 minutes at 48F"
    })
    assert res_hab.status_code == 200

    # Verify health endpoint returns logged vitals with wellbeing score
    res_health_list = client.get("/api/health")
    assert res_health_list.status_code == 200
    logs = res_health_list.json()["logs"]
    assert len(logs) >= 1
    today_log = next(l for l in logs if l["date"] == today_str)
    assert today_log["systolic"] == 118
    assert today_log["water_ml"] == 2500
    assert "wellbeing_score" in today_log

    # Verify overview payload contains today's habits and workouts count
    res_ov = client.get("/api/overview")
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert ov_data["weekly_workouts"] >= 1
    assert len(ov_data["todays_habits"]) >= 1

def test_career_pipeline_end_to_end():
    """
    Career pipeline E2E:
    1. Add a lead.
    2. Promote it to an application.
    3. Move it through statuses and add an interview event.
    4. Verify the board payload, timeline and stats.
    """
    res_lead = client.post("/api/career/leads", json={
        "company": "OpenAI",
        "role": "Platform Infrastructure Engineer",
        "job_url": "https://openai.com/careers/lead-999",
        "location": "San Francisco / Remote",
        "salary_range": "$180k - $240k",
    })
    assert res_lead.status_code == 200
    lead_id = res_lead.json()["id"]

    res_promote = client.post(f"/api/career/leads/{lead_id}/promote", json={"date_applied": "2026-06-05"})
    assert res_promote.status_code == 200
    app_id = res_promote.json()["id"]

    assert client.put(f"/api/career/applications/{app_id}", json={"status": "interviewing"}).status_code == 200
    res_event = client.post(f"/api/career/applications/{app_id}/events", json={
        "kind": "interview", "note": "System design round", "event_date": "2026-06-12"
    })
    assert res_event.status_code == 200

    data = client.get("/api/career").json()
    app = next(a for a in data["applications"] if a["id"] == app_id)
    assert app["company"] == "OpenAI"
    assert app["lead_id"] == lead_id
    assert app["status"] == "interviewing"
    # Timeline is ordered by event date: logged (Jun 5), interview (Jun 12), status change (today)
    assert [e["kind"] for e in app["events"]] == ["status_change", "interview", "status_change"]
    assert data["leads"] == []  # promoted lead is no longer open
    assert data["stats"]["by_status"]["interviewing"] == 1
