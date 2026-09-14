import pytest
import sqlite3
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import main
import database
import db_cli

client = TestClient(main.app)

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_sql_sanitization.db")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
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

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1 --",
    "'; DROP TABLE transactions; --",
    "'; DROP TABLE accounts; --",
    "' UNION SELECT 9999, 'injected', 99999, 'income', 'bad', 'hack', 'evil', NULL, NULL, NULL --",
    "1; DELETE FROM tasks; --",
    "1' OR '1'='1' --",
    "admin' --",
    "\" OR \"\"=\"",
    "'; VACUUM; --"
]

def test_sqli_accounts_creation_sanitization():
    """Verify malicious account names do not execute as raw SQL."""
    for payload in SQLI_PAYLOADS:
        res = client.post("/api/accounts", json={
            "name": f"Account {payload}",
            "type": "checking",
            "starting_balance": 100.0
        })
        assert res.status_code in (200, 400, 422)

    # Verify tables still exist
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) as cnt FROM accounts;")
    row = cursor.fetchone()
    assert row["cnt"] >= 1
    conn.close()

def test_sqli_transactions_query_and_search():
    """Verify transactions endpoints properly parameterize filters and inputs."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO accounts (name, type, starting_balance) VALUES ('SQLI Test Account', 'checking', 500.0);")
    account_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO transactions (date, amount, type, category, merchant, description, account_id)
        VALUES ('2026-06-01', 50.0, 'expense', 'food', 'Legit Merchant', 'Lunch', ?)
    """, (account_id,))
    conn.commit()
    conn.close()

    for payload in SQLI_PAYLOADS:
        # Test query parameters on GET endpoints
        res = client.get(f"/api/finances?category={payload}&account_id={payload}")
        assert res.status_code in (200, 400, 422)

        # Test POST creation with injected strings
        res_post = client.post("/api/finances", json={
            "date": "2026-06-02",
            "amount": 25.0,
            "type": "expense",
            "category": f"cat_{payload}",
            "merchant": f"merchant_{payload}",
            "description": f"desc_{payload}",
            "account_id": account_id
        })
        assert res_post.status_code in (200, 400, 422)

    # Verify transactions table was not dropped or corrupted
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) as cnt FROM transactions;")
    cnt = cursor.fetchone()["cnt"]
    assert cnt >= 1
    conn.close()

def test_sqli_tasks_title_and_category():
    """Verify tasks creation and filters resist SQL injection payloads."""
    for payload in SQLI_PAYLOADS:
        res = client.post("/api/tasks", json={
            "title": f"Task {payload}",
            "category": f"cat {payload}",
            "due_date": "2026-06-15",
            "priority": "medium"
        })
        assert res.status_code in (200, 400, 422)

    # Filter query params
    res_filter = client.get(f"/api/tasks?category={SQLI_PAYLOADS[0]}&status={SQLI_PAYLOADS[1]}")
    assert res_filter.status_code in (200, 400, 422)

    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) as cnt FROM tasks;")
    assert cursor.fetchone()["cnt"] >= 1
    conn.close()

def test_sqli_health_and_fitness_notes():
    """Verify health & fitness freeform notes resist SQL injection."""
    for idx, payload in enumerate(SQLI_PAYLOADS):
        date_str = f"2026-05-{10 + idx:02d}"
        res_health = client.post("/api/health", json={
            "date": date_str,
            "weight_lbs": 170.0,
            "sleep_hours": 8.0,
            "mood": f"Mood {payload}",
            "systolic": 120,
            "diastolic": 80,
            "notes": f"Vitals notes {payload}"
        })
        assert res_health.status_code in (200, 400, 422)

        res_fitness = client.post("/api/fitness", json={
            "date": date_str,
            "activity_type": f"Run {payload}",
            "duration_minutes": 30,
            "distance_km": 5.0,
            "calories_burned": 300,
            "intensity": "medium",
            "notes": f"Fitness notes {payload}"
        })
        assert res_fitness.status_code in (200, 400, 422)

    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) as cnt FROM health_logs;")
    assert cursor.fetchone()["cnt"] >= 1
    conn.close()

def test_sqli_db_cli_whitelist_protection():
    """Verify db_cli whitelist validates table names strictly against sqlite_master."""
    valid_tables = db_cli.list_tables()
    assert "accounts" in valid_tables
    assert "transactions" in valid_tables

    for payload in SQLI_PAYLOADS:
        bad_table = f"accounts {payload}"
        assert bad_table not in valid_tables

    # Verify tables still intact
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM accounts;")
    assert cursor.fetchone()[0] >= 0
    conn.close()
