import pytest
import os
import json
import sqlite3
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from database import get_db_connection, init_db
import agent

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_tasks_crud_with_estimates_and_subtasks():
    # 1. Create a task with estimates, recurrence, priority, and subtasks
    payload = {
        "title": "Build AI Model Pipeline",
        "category": "learning",
        "priority": "high",
        "importance": "major",
        "estimated_minutes": 45,
        "recurrence": "weekly",
        "subtasks": ["Collect dataset", "Train baseline", "Evaluate metrics"]
    }
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 200
    task_id = res.json()["id"]

    # 2. Get tasks and verify subtasks and fields
    res = client.get("/api/tasks")
    assert res.status_code == 200
    tasks = res.json()["tasks"]
    created_task = next((t for t in tasks if t["id"] == task_id), None)
    assert created_task is not None
    assert created_task["title"] == "Build AI Model Pipeline"
    assert created_task["estimated_minutes"] == 45
    assert created_task["priority"] == "high"
    assert created_task["recurrence"] == "weekly"
    assert len(created_task["subtasks"]) == 3
    assert created_task["subtasks"][0]["title"] == "Collect dataset"
    assert created_task["subtasks"][0]["is_completed"] == 0

    # 3. Toggle a subtask
    sub_id = created_task["subtasks"][0]["id"]
    res = client.put(f"/api/tasks/{task_id}/subtasks/{sub_id}", json={"is_completed": True})
    assert res.status_code == 200

    # Verify subtask is now completed
    res = client.get("/api/tasks")
    tasks = res.json()["tasks"]
    task_after = next(t for t in tasks if t["id"] == task_id)
    assert task_after["subtasks"][0]["is_completed"] == 1

    # Cleanup
    client.delete(f"/api/tasks/{task_id}")

def test_task_prerequisites_blocking():
    # Create prerequisite task
    res_prereq = client.post("/api/tasks", json={"title": "Draft proposal", "priority": "medium"})
    prereq_id = res_prereq.json()["id"]

    # Create dependent task
    res_dep = client.post("/api/tasks", json={
        "title": "Send proposal to client", 
        "priority": "high",
        "prerequisites": [{"prerequisite_type": "task", "prerequisite_id": prereq_id}]
    })
    dep_id = res_dep.json()["id"]

    # Dependent task should be blocked
    res = client.get("/api/tasks")
    tasks = res.json()["tasks"]
    dep_task = next(t for t in tasks if t["id"] == dep_id)
    assert dep_task["is_blocked"] is True
    assert len(dep_task["unmet_prerequisites"]) > 0

    # Mark prerequisite task as completed
    client.put(f"/api/tasks/{prereq_id}/toggle")

    # Dependent task should now be unblocked
    res = client.get("/api/tasks")
    tasks = res.json()["tasks"]
    dep_task = next(t for t in tasks if t["id"] == dep_id)
    assert dep_task["is_blocked"] is False
    assert len(dep_task["unmet_prerequisites"]) == 0

    # Cleanup
    client.delete(f"/api/tasks/{prereq_id}")
    client.delete(f"/api/tasks/{dep_id}")

def test_calendar_events_and_gap_recommendations():
    test_date = "2026-10-15"
    
    # Create two events on test_date: 09:00-10:00 and 11:00-12:00 (leaving 10:00-11:00 free: 60 mins gap)
    ev1_payload = {
        "title": "Morning Sync",
        "start_time": f"{test_date} 09:00:00",
        "end_time": f"{test_date} 10:00:00",
        "tags": ["#Work", "#Meeting"],
        "color": "#ff007f",
        "sync_to_google": False
    }
    ev2_payload = {
        "title": "Deep Architecture",
        "start_time": f"{test_date} 11:00:00",
        "end_time": f"{test_date} 12:00:00",
        "tags": ["#Engineering"],
        "color": "#00f0ff",
        "sync_to_google": False
    }
    r1 = client.post("/api/calendar", json=ev1_payload)
    r2 = client.post("/api/calendar", json=ev2_payload)
    ev1_id = r1.json()["id"]
    ev2_id = r2.json()["id"]

    # Create tasks: one 30m (fits in gap) and one 90m (doesn't fit in gap)
    t1 = client.post("/api/tasks", json={"title": "Quick Review", "estimated_minutes": 30, "priority": "high"}).json()["id"]
    t2 = client.post("/api/tasks", json={"title": "Long Refactor", "estimated_minutes": 90, "priority": "medium"}).json()["id"]

    # Query gaps
    res = client.get(f"/api/calendar/gaps?date={test_date}&day_start=08:00&day_end=13:00")
    assert res.status_code == 200
    gaps = res.json()["gaps"]

    # There should be a gap from 10:00 to 11:00 (60 mins)
    gap_60 = next((g for g in gaps if g["start"] == "10:00" and g["end"] == "11:00"), None)
    assert gap_60 is not None
    assert gap_60["duration_minutes"] == 60
    # Quick Review (30m) should be recommended; Long Refactor (90m) should not
    recommended_titles = [t["title"] for t in gap_60["recommended_tasks"]]
    assert "Quick Review" in recommended_titles
    assert "Long Refactor" not in recommended_titles

    # Cleanup
    client.delete(f"/api/calendar/{ev1_id}")
    client.delete(f"/api/calendar/{ev2_id}")
    client.delete(f"/api/tasks/{t1}")
    client.delete(f"/api/tasks/{t2}")

def test_archive_and_reset_tasks_nightly():
    # Create a daily recurring task (completed) and a one-off task (completed)
    r_daily = client.post("/api/tasks", json={"title": "Morning Stretch", "recurrence": "daily"}).json()["id"]
    client.put(f"/api/tasks/{r_daily}/toggle") # mark completed

    r_oneoff = client.post("/api/tasks", json={"title": "One-off errand", "recurrence": "none"}).json()["id"]
    client.put(f"/api/tasks/{r_oneoff}/toggle") # mark completed

    # Run archive_and_reset_tasks_nightly
    agent.archive_and_reset_tasks_nightly()

    # Verify: one-off task should be removed from database
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id = ?", (r_oneoff,))
    assert c.fetchone() is None

    # Daily recurring task should still exist, reset to pending
    c.execute("SELECT * FROM tasks WHERE id = ?", (r_daily,))
    daily_row = c.fetchone()
    assert daily_row is not None
    assert daily_row["status"] == "pending"
    assert daily_row["completed_at"] is None

    conn.close()
    client.delete(f"/api/tasks/{r_daily}")
