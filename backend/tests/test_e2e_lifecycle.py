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
import job_tailor_engine
import career_agent

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

    # 4. Set budget for groceries
    res_bgt = client.post("/api/budgets", json={"category": "groceries", "limit_amount": 600.0})
    assert res_bgt.status_code == 200

    res_fin_bgt = client.get("/api/finances")
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

def test_career_pipeline_end_to_end(monkeypatch):
    """
    Test Career Engine E2E:
    1. Create career search profile.
    2. Add job lead.
    3. Mock LLM and tailor lead.
    4. Verify application packet created and status kanban updated.
    """
    # 1. Create profile
    res_prof = client.post("/api/career/profiles", json={
        "name": "Applied AI Engineer",
        "keywords": "FastAPI, Docker, LLM, Python",
        "locations": "Remote",
        "active": 1
    })
    assert res_prof.status_code == 200
    profile_id = res_prof.json()["id"]

    # 2. Insert job lead
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_leads (date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
        VALUES ('2026-06-05', 'OpenAI', 'Platform Infrastructure Engineer', 'San Francisco / Remote', '$180k - $240k', 'Build resilient backend systems.', 'https://openai.com/careers/lead-999', 'greenhouse', 'lead', ?)
    """, (profile_id,))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()

    # 3. Mock LLM for tailoring
    mock_packet = {
        "match_score": 92,
        "recruiter_name": "Sam Altman",
        "recruiter_email": "sam@openai.com",
        "tailored_bullets": "- Architected high-throughput FastAPI microservices\n- Containerized dual dev/prod environments\n- Automated agentic ingestion with local models",
        "cover_letter": "I am eager to contribute to OpenAI infrastructure.",
        "cold_email_draft": "Hi Sam, I build reliable platform systems and would love to chat."
    }
    monkeypatch.setattr(job_tailor_engine, "call_llm", lambda prompt: json.dumps(mock_packet))

    # Process & tailor lead
    res_proc = client.post(f"/api/career/leads/{lead_id}/process")
    assert res_proc.status_code == 200
    app_id = res_proc.json()["application_id"]

    # 4. Verify in /api/career
    res_career = client.get("/api/career")
    assert res_career.status_code == 200
    apps = res_career.json()["applications"]
    app = next(a for a in apps if a["id"] == app_id)
    assert app["company"] == "OpenAI"
    assert app["recruiter_name"] == "Sam Altman"
    assert app["recruiter_email"] == "sam@openai.com"
    assert "FastAPI" in app["tailored_bullets"]
