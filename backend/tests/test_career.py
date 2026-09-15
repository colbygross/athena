import pytest
import os
import sys
import json

# Add backend directory to sys.path to ensure database import works
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

TEST_DB_PATH = os.path.join(backend_dir, "tests", "test_career_life_dashboard.db")
import database
database.DB_PATH = TEST_DB_PATH



import main
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Ensure the test database is re-initialized for each test."""
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    database.init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_career_profiles_endpoints():
    # 1. Get initial profiles (should be empty)
    res = client.get("/api/career")
    assert res.status_code == 200
    data = res.json()
    assert "profiles" in data
    assert "leads" in data
    assert "applications" in data
    assert len(data["profiles"]) == 0
    assert len(data["leads"]) == 0

    # 2. Add profile
    profile = {
        "name": "Cybersecurity Track",
        "keywords": "SOC Analyst, Network Security",
        "locations": "Boston MA, Remote",
        "resume_path": "./storage/sample_resume.html",
        "active": 1
    }
    res = client.post("/api/career/profiles", json=profile)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "success"
    profile_id = res_data["id"]

    # 3. Verify added
    res = client.get("/api/career")
    data = res.json()
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["name"] == "Cybersecurity Track"
    assert data["profiles"][0]["id"] == profile_id

    # 4. Delete profile
    res = client.delete(f"/api/career/profiles/{profile_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 5. Verify deleted
    res = client.get("/api/career")
    assert len(res.json()["profiles"]) == 0

def test_job_leads_endpoints():
    # Setup: add profile
    profile = {
        "name": "Agentic AI Track",
        "keywords": "AI Developer",
        "locations": "Remote",
        "active": 1
    }
    res = client.post("/api/career/profiles", json=profile)
    profile_id = res.json()["id"]

    # 1. Inject a lead manually to DB
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_leads (date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
        VALUES ('2026-07-13', 'Google', 'AI Agent Engineer', 'Remote', '$150k', 'Build cool agents.', 'https://google.com/jobs/123', 'linkedin', 'lead', ?)
    """, (profile_id,))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()

    # 2. Verify lead is returned
    res = client.get("/api/career")
    data = res.json()
    assert len(data["leads"]) == 1
    assert data["leads"][0]["company"] == "Google"
    assert data["leads"][0]["role"] == "AI Agent Engineer"

    # 3. Ignore lead
    res = client.post(f"/api/career/leads/{lead_id}/ignore")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify no leads returned
    res = client.get("/api/career")
    assert len(res.json()["leads"]) == 0

def test_process_lead_and_tailoring(monkeypatch):
    # Setup: add profile
    profile = {
        "name": "Agentic AI Track",
        "keywords": "AI Developer",
        "locations": "Remote",
        "active": 1
    }
    profile_id = client.post("/api/career/profiles", json=profile).json()["id"]

    # Insert lead
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_leads (date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
        VALUES ('2026-07-13', 'Google', 'AI Agent Engineer', 'Remote', '$150k', 'Build cool agents.', 'https://google.com/jobs/123', 'linkedin', 'lead', ?)
    """, (profile_id,))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()

    # Mock the LLM call inside career_agent
    mock_llm_response = {
        "recruiter_name": "Sundar Pichai",
        "recruiter_email": "sundar@google.com",
        "tailored_bullets": "- Custom agent project built using Antigravity.",
        "cover_letter": "I want to build agents at Google.",
        "cold_email_draft": "Hi Sundar, I build agents. Proposing slot times."
    }
    
    import career_agent
    import job_tailor_engine
    monkeypatch.setattr(career_agent, "call_llm", lambda prompt: json.dumps(mock_llm_response))
    monkeypatch.setattr(job_tailor_engine, "call_llm", lambda prompt: json.dumps(mock_llm_response))
    monkeypatch.setattr(career_agent, "search_web_recruiter", lambda comp: ["Sundar Pichai"])

    # 1. Process lead
    res = client.post(f"/api/career/leads/{lead_id}/process")
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "success"
    app_id = res_data["application_id"]

    # 2. Verify application logged
    res = client.get("/api/career")
    data = res.json()
    assert len(data["applications"]) == 1
    app = data["applications"][0]
    assert app["id"] == app_id
    assert app["company"] == "Google"
    assert app["recruiter_name"] == "Sundar Pichai"
    assert app["recruiter_email"] == "sundar@google.com"
    assert app["cold_email_draft"] == "Hi Sundar, I build agents. Proposing slot times."
    assert app["tailored_bullets"] == "- Custom agent project built using Antigravity."

    # 3. Update application fields
    updated_data = {
        "recruiter_name": "Larry Page",
        "recruiter_email": "larry@google.com"
    }
    res = client.put(f"/api/career/applications/{app_id}", json=updated_data)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify update
    res = client.get("/api/career")
    app = res.json()["applications"][0]
    assert app["recruiter_name"] == "Larry Page"
    assert app["recruiter_email"] == "larry@google.com"
