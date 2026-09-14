import pytest
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import main
import database
import agent

client = TestClient(main.app)

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_security_audit.db")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    temp_vault = tmp_path / "obsidian_vault"
    temp_vault.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    
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

def test_cors_origin_spoofing_prevention():
    """Verify malicious or spoofed origins are blocked by CORS logic."""
    malicious_origins = [
        "http://attacker.com",
        "http://localhost.evil.com",
        "http://127.0.0.1.attacker.com",
        "http://my-desktop.ts.net.attacker.com",
        "http://192.168.1.100.attacker.com",
        "null"
    ]
    for origin in malicious_origins:
        assert main.is_allowed_origin(origin) is False
        res = client.get("/api/overview", headers={"Origin": origin})
        assert res.headers.get("access-control-allow-origin") != origin

def test_cors_valid_origins():
    """Verify legitimate localhost and tailnet origins are properly allowed."""
    valid_origins = [
        "http://localhost",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://archer-node.ts.net:8000",
        "https://my-phone.tailscale.net"
    ]
    for origin in valid_origins:
        assert main.is_allowed_origin(origin) is True

def test_path_traversal_projects_endpoint():
    """Verify path traversal payloads in project notes are strictly rejected."""
    traversal_filenames = [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "subdir/../../../etc/shadow",
        "..\\..\\windows\\win.ini",
        "/etc/passwd"
    ]
    for fname in traversal_filenames:
        res_get = client.get(f"/api/projects/{fname}")
        assert res_get.status_code in (400, 404)
        
        res_post = client.post(f"/api/projects/{fname}", json={"content": "hacked"})
        assert res_post.status_code in (400, 404)

def test_path_traversal_areas_endpoint():
    """Verify path traversal payloads in areas category and filename are blocked."""
    traversal_cases = [
        ("..", "passwd"),
        ("Fitness", "something/with/slashes"),
        ("..", ".."),
        ("invalid..cat", "notes.md")
    ]
    for cat, fname in traversal_cases:
        res = client.post(f"/api/areas/{cat}/{fname}", json={"content": "injected"})
        assert res.status_code in (400, 404, 405)

def test_pydantic_payload_numerical_integrity():
    """Verify invalid or extreme amounts and types are rejected with 422 Unprocessable Entity."""
    # Invalid account type rejected by database check constraint
    res = client.post("/api/accounts", json={
        "name": "Invalid Type Account",
        "type": "crypto_scam",  # Check constraint: checking, savings, credit_card, investment, cash
        "starting_balance": 100.0
    })
    assert res.status_code in (400, 422, 500)

    # String as amount
    res = client.post("/api/finances", json={
        "date": "2026-06-01",
        "amount": "not_a_number",
        "type": "expense",
        "category": "food",
        "account_id": 1
    })
    assert res.status_code == 422

    # String as duration_minutes in fitness log
    res = client.post("/api/fitness", json={
        "date": "2026-06-01",
        "activity_type": "run",
        "duration_minutes": "thirty",
        "intensity": "medium"
    })
    assert res.status_code == 422
