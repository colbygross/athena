import json
import os
import sqlite3
import sys

import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import career
import database
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "career.db"))
    monkeypatch.setattr(database, "STORAGE_DIR", str(tmp_path / "storage"))
    database.init_db()
    yield


def _conn():
    return database.create_new_connection()


def test_log_application_creates_with_timeline():
    res = client.post("/api/career", json={"company": "Acme", "role": "SWE", "job_description_url": "https://acme.jobs/1"})
    assert res.status_code == 200
    assert res.json()["result"] == "created"
    app = client.get(f"/api/career/applications/{res.json()['id']}").json()
    assert app["status"] == "applied"
    assert [e["note"] for e in app["events"]] == ["Logged as applied"]


def test_log_application_upserts_by_url_then_company_role():
    first = client.post("/api/career", json={"company": "Acme", "role": "SWE", "job_description_url": "https://acme.jobs/1/"}).json()
    by_url = client.post("/api/career", json={"company": "Acme Inc", "role": "Engineer", "job_description_url": "https://acme.jobs/1", "notes": "n"}).json()
    by_name = client.post("/api/career", json={"company": " acme ", "role": "swe", "salary_range": "$100k"}).json()
    assert by_url == {"status": "success", "id": first["id"], "result": "updated"}
    assert by_name["id"] == first["id"] and by_name["result"] == "updated"
    app = client.get(f"/api/career/applications/{first['id']}").json()
    assert app["notes"] == "n" and app["salary_range"] == "$100k"
    assert len(client.get("/api/career").json()["applications"]) == 1


def test_company_role_match_respects_window():
    client.post("/api/career", json={"company": "Acme", "role": "SWE", "date_applied": "2026-01-01"})
    later = client.post("/api/career", json={"company": "Acme", "role": "SWE", "date_applied": "2026-06-01"}).json()
    assert later["result"] == "created"


def test_relogging_never_moves_status_backwards():
    app_id = client.post("/api/career", json={"company": "Acme", "role": "SWE"}).json()["id"]
    client.put(f"/api/career/applications/{app_id}", json={"status": "interviewing"})
    client.post("/api/career", json={"company": "Acme", "role": "SWE", "notes": "re-logged"})
    assert client.get(f"/api/career/applications/{app_id}").json()["status"] == "interviewing"


def test_status_change_recorded_and_validated():
    app_id = client.post("/api/career", json={"company": "Acme", "role": "SWE"}).json()["id"]
    assert client.put(f"/api/career/applications/{app_id}", json={"status": "hired"}).status_code == 400
    assert client.put(f"/api/career/applications/{app_id}", json={"status": "offered"}).status_code == 200
    events = client.get(f"/api/career/applications/{app_id}").json()["events"]
    assert events[-1]["kind"] == "status_change" and "applied → offered" in events[-1]["note"]


def test_validation_and_not_found():
    assert client.post("/api/career", json={"company": " ", "role": "SWE"}).status_code == 400
    assert client.post("/api/career", json={"company": "A", "role": "B", "date_applied": "June 1"}).status_code == 400
    assert client.get("/api/career/applications/999").status_code == 404
    assert client.post("/api/career/applications/999/events", json={"kind": "note"}).status_code == 404
    assert client.post("/api/career/leads/999/promote").status_code == 404
    app_id = client.post("/api/career", json={"company": "A", "role": "B"}).json()["id"]
    assert client.post(f"/api/career/applications/{app_id}/events", json={"kind": "party"}).status_code == 400


def test_leads_add_upsert_dismiss_promote():
    lead = client.post("/api/career/leads", json={"company": "Beta", "role": "ML Eng", "job_url": "https://beta.jobs/9"}).json()
    again = client.post("/api/career/leads", json={"company": "Beta", "role": "ML Engineer", "job_url": "https://beta.jobs/9/"}).json()
    assert again["id"] == lead["id"] and again["result"] == "updated"
    other = client.post("/api/career/leads", json={"company": "Gamma", "role": "SRE", "job_url": "https://g.jobs/1"}).json()
    assert client.post(f"/api/career/leads/{other['id']}/ignore").status_code == 200

    promoted = client.post(f"/api/career/leads/{lead['id']}/promote", json={"notes": "applied via site"}).json()
    data = client.get("/api/career").json()
    assert data["leads"] == []
    app = next(a for a in data["applications"] if a["id"] == promoted["id"])
    assert app["lead_id"] == lead["id"] and app["role"] == "ML Engineer"
    assert app["job_description_url"] == "https://beta.jobs/9"


def test_delete_application_removes_events():
    app_id = client.post("/api/career", json={"company": "A", "role": "B"}).json()["id"]
    assert client.delete(f"/api/career/applications/{app_id}").status_code == 200
    conn = _conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM application_events").fetchone()[0] == 0
    finally:
        conn.close()


def test_retire_job_hunt_schema_backs_up_and_migrates(tmp_path, monkeypatch):
    """A database from before the redesign keeps its rows; retired data lands in a JSON backup."""
    db_path = tmp_path / "old.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    old = sqlite3.connect(db_path)
    old.executescript("""
        CREATE TABLE career_search_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, keywords TEXT, locations TEXT, active INTEGER);
        CREATE TABLE job_leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date_found TEXT NOT NULL, company TEXT NOT NULL, role TEXT NOT NULL,
            location TEXT, salary_range TEXT, job_description TEXT, job_url TEXT UNIQUE NOT NULL,
            source TEXT CHECK(source IN ('linkedin', 'greenhouse')) NOT NULL, status TEXT DEFAULT 'lead',
            profile_id INTEGER REFERENCES career_search_profiles(id) ON DELETE CASCADE);
        CREATE TABLE job_applications (id INTEGER PRIMARY KEY AUTOINCREMENT, date_applied TEXT NOT NULL, company TEXT NOT NULL,
            role TEXT NOT NULL, salary_range TEXT, status TEXT DEFAULT 'applied', job_description_url TEXT, notes TEXT,
            resume_file_id INTEGER, lead_id INTEGER REFERENCES job_leads(id) ON DELETE SET NULL, recruiter_name TEXT,
            recruiter_email TEXT, cold_email_draft TEXT, outreach_status TEXT DEFAULT 'pending', tailored_bullets TEXT, cover_letter TEXT);
        CREATE TABLE outreach_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER, recipient_email TEXT, subject TEXT, body TEXT);
        INSERT INTO career_search_profiles (name, keywords, locations, active) VALUES ('p', 'k', 'l', 1);
        INSERT INTO job_leads (date_found, company, role, job_url, source, profile_id) VALUES ('2026-01-01', 'Acme', 'SWE', 'https://a/1', 'greenhouse', 1);
        INSERT INTO job_applications (date_applied, company, role, lead_id, recruiter_email, cover_letter) VALUES ('2026-01-02', 'Acme', 'SWE', 1, 'r@a.com', 'Dear...');
        INSERT INTO outreach_logs (application_id, recipient_email, subject, body) VALUES (1, 'r@a.com', 's', 'b');
    """)
    old.commit()
    old.close()

    database.init_db()
    database.init_db()  # idempotent

    conn = _conn()
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not tables & {"career_search_profiles", "outreach_logs", "job_leads_new", "job_applications_new"}
        app_cols = {r[1] for r in conn.execute("PRAGMA table_info(job_applications)")}
        assert not app_cols & set(database.RETIRED_APPLICATION_COLUMNS)
        assert "profile_id" not in {r[1] for r in conn.execute("PRAGMA table_info(job_leads)")}
        app = dict(conn.execute("SELECT * FROM job_applications").fetchone())
        assert app["lead_id"] == 1 and app["recruiter_email"] == "r@a.com"
        assert conn.execute("SELECT COUNT(*) FROM job_leads").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Leads accept any source now
        career.add_lead(conn, "Beta", "SRE", "https://b/1", source="claude-code")
    finally:
        conn.close()

    backups = os.listdir(database.STORAGE_DIR)
    assert len(backups) == 1
    with open(os.path.join(database.STORAGE_DIR, backups[0])) as f:
        backup = json.load(f)
    assert backup["job_applications"][0]["cover_letter"] == "Dear..."
    assert backup["outreach_logs"][0]["subject"] == "s"
    assert backup["career_search_profiles"][0]["name"] == "p"
