import os
import shutil
import sqlite3
import pytest
import re
import ipaddress
from urllib.parse import urlparse
from fastapi.testclient import TestClient

# Add backend directory to sys.path
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_e2e_life_dashboard.db")
import database
database.DB_PATH = TEST_DB_PATH

import agent
import main
from main import app

client = TestClient(app)

TEST_SECRET_API_KEY = "athena-test-secure-api-key-2026"

# --- FIXTURES ---

@pytest.fixture(autouse=True)
def setup_isolation(monkeypatch, tmp_path):
    """
    Sets up separate temporary environments for the database and the Obsidian Vault.
    """
    # 1. Database isolation
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    database.init_db()

    # 2. Vault files isolation
    temp_vault = tmp_path / "obsidian_vault"
    temp_inbox = temp_vault / "Inbox"
    temp_storage = tmp_path / "storage"
    
    temp_inbox.mkdir(parents=True)
    temp_storage.mkdir()
    
    # Create required folder structures in vault
    (temp_vault / "Daily_Briefs").mkdir(parents=True, exist_ok=True)
    (temp_vault / "04_Archives").mkdir(parents=True, exist_ok=True)
    (temp_vault / "Summaries").mkdir(parents=True, exist_ok=True)
    (temp_vault / "02_Areas" / "Finances").mkdir(parents=True, exist_ok=True)
    (temp_vault / "02_Areas" / "Health").mkdir(parents=True, exist_ok=True)
    (temp_vault / "02_Areas" / "Fitness").mkdir(parents=True, exist_ok=True)
    (temp_vault / "01_Projects").mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    monkeypatch.setattr(agent, "INBOX_DIR", str(temp_inbox))
    monkeypatch.setattr(agent, "STORAGE_DIR", str(temp_storage))
    monkeypatch.setattr(agent, "LLM_ENABLED", False)
    
    # Enable API authentication
    monkeypatch.setenv("API_KEY", TEST_SECRET_API_KEY)
    monkeypatch.setattr(main, "API_KEY", TEST_SECRET_API_KEY)

    yield temp_vault, temp_inbox, temp_storage
    
    # Clean up DB
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

@pytest.fixture
def atomic_file_spy(monkeypatch):
    replace_calls = []
    rename_calls = []
    move_calls = []

    orig_replace = os.replace
    def mock_replace(src, dst, *args, **kwargs):
        with open(src, "rb") as f:
            content = f.read()
        replace_calls.append({"src": src, "dst": dst, "content": content})
        return orig_replace(src, dst, *args, **kwargs)
    monkeypatch.setattr(os, "replace", mock_replace)

    orig_rename = os.rename
    def mock_rename(src, dst, *args, **kwargs):
        with open(src, "rb") as f:
            content = f.read()
        rename_calls.append({"src": src, "dst": dst, "content": content})
        return orig_rename(src, dst, *args, **kwargs)
    monkeypatch.setattr(os, "rename", mock_rename)

    orig_move = shutil.move
    def mock_move(src, dst, *args, **kwargs):
        content = b""
        if os.path.exists(src) and os.path.isfile(src):
            with open(src, "rb") as f:
                content = f.read()
        move_calls.append({"src": src, "dst": dst, "content": content})
        return orig_move(src, dst, *args, **kwargs)
    monkeypatch.setattr(shutil, "move", mock_move)

    class SpyRegistry:
        @property
        def replace(self): return replace_calls
        @property
        def rename(self): return rename_calls
        @property
        def move(self): return move_calls
        
        def assert_atomic_write(self, expected_dest, expected_content_substring=None):
            all_calls = replace_calls + rename_calls + move_calls
            matching_calls = [c for c in all_calls if os.path.abspath(c["dst"]) == os.path.abspath(expected_dest)]
            assert len(matching_calls) >= 1, f"No atomic write recorded for {expected_dest}"
            
            for call in matching_calls:
                src_name = os.path.basename(call["src"])
                dst_name = os.path.basename(call["dst"])
                assert src_name != dst_name, f"Direct write detected instead of atomic write: src='{src_name}' dst='{dst_name}'"
                assert os.path.dirname(os.path.abspath(call["src"])) == os.path.dirname(os.path.abspath(call["dst"])), \
                    "Temp file was not created in the same parent directory"
                if expected_content_substring is not None:
                    assert expected_content_substring in call["content"].decode("utf-8")
                        
    return SpyRegistry()

@pytest.fixture
def db_query_counter(monkeypatch):
    captured_connections = []
    
    def mock_get_db_connection():
        conn = sqlite3.connect(database.DB_PATH, factory=QueryCountingConnection)
        conn.row_factory = sqlite3.Row
        captured_connections.append(conn)
        return conn

    monkeypatch.setattr(database, "get_db_connection", mock_get_db_connection)
    
    class CounterRegistry:
        @property
        def total_queries(self):
            return sum(conn.total_query_count for conn in captured_connections)
            
        @property
        def executed_queries(self):
            all_q = []
            for conn in captured_connections:
                all_q.extend(conn.queries_list)
            return all_q
            
        def reset(self):
            captured_connections.clear()
            
    return CounterRegistry()

# Custom Query Counting Connection Classes
class QueryCountingCursor(sqlite3.Cursor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query_count = 0
        self.queries = []

    def execute(self, sql, parameters=None):
        self.query_count += 1
        self.queries.append((sql, parameters))
        if parameters is not None:
            return super().execute(sql, parameters)
        return super().execute(sql)

    def executemany(self, sql, seq_of_parameters):
        self.query_count += 1
        self.queries.append((sql, seq_of_parameters))
        return super().executemany(sql, seq_of_parameters)

class QueryCountingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured_cursors = []

    def cursor(self, *args, **kwargs):
        cur = super().cursor(QueryCountingCursor, **kwargs)
        self.captured_cursors.append(cur)
        return cur

    @property
    def total_query_count(self):
        return sum(c.query_count for c in self.captured_cursors)

    @property
    def queries_list(self):
        all_q = []
        for c in self.captured_cursors:
            all_q.extend(c.queries)
        return all_q


# --- F1: SQLite Foreign Key Constraints Enforcement Tests ---

def test_f1_foreign_key_blocking():
    """Verify orphaned inserts violating FK constraints are blocked."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Verify insert of transaction referencing non-existent account ID fails
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO transactions (date, amount, type, category, account_id) VALUES (?, ?, ?, ?, ?)",
            ("2026-06-09", 10.0, "expense", "food", 99999)
        )
    conn.close()

def test_f1_cascade_behaviors():
    """Verify that deleting an account handles cascades correctly (set null vs delete)."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create an account
    cursor.execute("INSERT INTO accounts (name, type, starting_balance) VALUES (?, ?, ?)", ("E2E Test Account", "checking", 100.0))
    account_id = cursor.lastrowid
    
    # 2. Add transaction linking to this account (ON DELETE SET NULL)
    cursor.execute(
        "INSERT INTO transactions (date, amount, type, category, account_id) VALUES (?, ?, ?, ?, ?)",
        ("2026-06-09", 50.0, "expense", "utilities", account_id)
    )
    tx_id = cursor.lastrowid
    
    # 3. Add recurring transaction linking to this account (ON DELETE CASCADE)
    cursor.execute(
        "INSERT INTO recurring_transactions (name, amount, interval, category, account_id, next_due_date) VALUES (?, ?, ?, ?, ?, ?)",
        ("Netflix Premium", 15.0, "monthly", "subscription", account_id, "2026-07-01")
    )
    rec_id = cursor.lastrowid
    conn.commit()
    
    # 4. Delete the account
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    
    # 5. Assert transactions' account_id was set to NULL
    cursor.execute("SELECT account_id FROM transactions WHERE id = ?", (tx_id,))
    tx_account_id = cursor.fetchone()[0]
    assert tx_account_id is None
    
    # 6. Assert recurring transaction was cascade-deleted
    cursor.execute("SELECT COUNT(*) FROM recurring_transactions WHERE id = ?", (rec_id,))
    rec_count = cursor.fetchone()[0]
    assert rec_count == 0
    
    conn.close()


# --- F2: Database Indexes Verification Tests ---

@pytest.mark.parametrize("query, expected_index", [
    ("SELECT * FROM transactions WHERE date = '2026-06-09'", "idx_transactions_date"),
    ("SELECT * FROM transactions WHERE account_id = 1", "idx_transactions_account_id"),
    ("SELECT * FROM transactions WHERE transfer_account_id = 2", "idx_transactions_transfer_account_id"),
    ("SELECT * FROM fitness_logs WHERE date = '2026-06-09'", "idx_fitness_logs_date"),
    ("SELECT * FROM learning_progress WHERE date = '2026-06-09'", "idx_learning_progress_date"),
    ("SELECT * FROM meal_logs WHERE date = '2026-06-09'", "idx_meal_logs_date"),
    ("SELECT * FROM mindfulness_logs WHERE date = '2026-06-09'", "idx_mindfulness_logs_date"),
    ("SELECT * FROM job_applications WHERE date_applied = '2026-06-09'", "idx_job_applications_date_applied"),
    ("SELECT * FROM job_applications WHERE status = 'applied'", "idx_job_applications_status"),
    ("SELECT * FROM tasks WHERE status = 'pending' AND due_date = '2026-06-09'", "idx_tasks_status_due_date"),
    ("SELECT * FROM tasks WHERE status = 'pending' AND completed_at = '2026-06-09'", "idx_tasks_status_completed_at"),
    ("SELECT * FROM recurring_transactions WHERE account_id = 1", "idx_recurring_transactions_account_id"),
    ("SELECT * FROM calendar_events WHERE start_time = '2026-06-09'", "idx_calendar_events_start_time"),
    ("SELECT * FROM tasks WHERE source_file = '01_Projects/My Project.md'", "idx_tasks_source_file"),
])
def test_f2_indexes_usage(query, expected_index):
    """Verify that indices exist and are utilized by SQLite EXPLAIN QUERY PLAN."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Verify index exists in sqlite_master
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (expected_index,))
    idx = cursor.fetchone()
    assert idx is not None, f"Index {expected_index} does not exist in sqlite_master"
    
    # Verify query planner uses the index
    cursor.execute(f"EXPLAIN QUERY PLAN {query}")
    plan = "\n".join([row[3] for row in cursor.fetchall()])
    assert f"USING INDEX {expected_index}" in plan or f"USING COVERING INDEX {expected_index}" in plan, \
        f"Query '{query}' did not use index '{expected_index}'. Plan:\n{plan}"
        
    conn.close()


# --- F3: Robust Task Toggle Logic Tests ---

def test_f3_exact_task_toggling(setup_isolation):
    """Verify exact task toggling handles strings with tags and date correctly, avoiding substring matches."""
    temp_vault = setup_isolation[0]
    tasks_file = os.path.join(str(temp_vault), "tasks.md")
    
    # Seed tasks.md
    initial_content = (
        "# Athena Tasks\n\n"
        "- [ ] Verify backup 📅 2026-06-09 #high\n"
        "- [ ] Backup\n"
    )
    with open(tasks_file, "w", encoding="utf-8") as f:
        f.write(initial_content)
        
    # Toggle "Backup" (mark completed)
    success = agent.toggle_task_in_file(str(temp_vault), "tasks.md", "Backup", mark_completed=True)
    assert success is True
    
    with open(tasks_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # Verify "Backup" is completed, but "Verify backup" remains pending
    assert "- [x] Backup\n" in lines
    assert "- [ ] Verify backup 📅 2026-06-09 #high\n" in lines
    
    # Toggle "Verify backup" (mark completed)
    success2 = agent.toggle_task_in_file(str(temp_vault), "tasks.md", "Verify backup", mark_completed=True)
    assert success2 is True
    
    with open(tasks_file, "r", encoding="utf-8") as f:
        lines2 = f.readlines()
        
    assert "- [x] Verify backup 📅 2026-06-09 #high\n" in lines2


# --- F4: Atomic File Sync System Tests ---

@pytest.mark.parametrize("write_op, rel_path, substring", [
    ("daily_brief", "Daily_Briefs/Daily_Brief_2026-06-09.md", "Daily Brief"),
    ("daily_summary", "04_Archives/Daily_Summary_2026-06-08.md", "Daily Summary"),
    ("note", "02_Areas/Finances/2026-06-09_Starbucks_receipt.md", "Processed and synchronized"),
    ("financial_summary", "Summaries/Financial_Summary.md", "# Weekly Financial Summary"),
    ("health_summary", "Summaries/Health_Fitness_Summary.md", "# Fitness & Health Summary"),
    ("learning_summary", "Summaries/Learning_Career_Summary.md", "# Learning & Career Tracker"),
    ("calendar_ics", "calendar.ics", "BEGIN:VCALENDAR"),
    ("tasks_md", "tasks.md", "Athena Tasks"),
])
def test_f4_atomic_writes_success(write_op, rel_path, substring, atomic_file_spy, setup_isolation):
    """Verify that file writes for briefs, summaries, index summaries, notes, calendar, and task lists are atomic."""
    temp_vault = setup_isolation[0]
    if write_op == "daily_brief":
        import datetime
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        rel_path = f"Daily_Briefs/Daily_Brief_{today_str}.md"
    dest_path = os.path.join(str(temp_vault), rel_path)
    
    # Pre-seed tasks.md to have a valid file to read for tasks_md and daily_brief
    with open(os.path.join(str(temp_vault), "tasks.md"), "w", encoding="utf-8") as f:
        f.write("# Athena Tasks\n\n- [ ] Clean keyboard\n")
        
    if write_op == "daily_brief":
        agent.generate_daily_brief()
    elif write_op == "daily_summary":
        agent.generate_daily_summary(target_date="2026-06-08")
    elif write_op == "note":
        analysis = {
            "original_name": "Starbucks_receipt.jpg",
            "category": "finances",
            "description": "Starbucks receipt",
            "structured_data": {"date": "2026-06-09", "amount": 4.50, "merchant": "Starbucks"}
        }
        dest_dir = os.path.join(str(temp_vault), "02_Areas", "Finances")
        agent.create_obsidian_note(analysis, dest_dir, "2026-06-09_Starbucks_receipt.jpg")
    elif write_op == "financial_summary" or write_op == "health_summary" or write_op == "learning_summary":
        agent.generate_obsidian_summaries()
    elif write_op == "calendar_ics":
        agent.serialize_local_events_to_ics_helper()
    elif write_op == "tasks_md":
        agent.sync_db_to_tasks_md_helper()
        
    atomic_file_spy.assert_atomic_write(dest_path, substring)

def test_f4_write_error_atomicity(monkeypatch, setup_isolation):
    """Verify that a write error mid-operation leaves the target file unmodified and intact."""
    temp_vault = setup_isolation[0]
    import datetime
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    brief_path = os.path.join(str(temp_vault), "Daily_Briefs", f"Daily_Brief_{today_str}.md")
    
    # 1. Pre-seed the brief
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write("Original Brief Content")
        
    # 2. Mock atomic helper to fail during execution
    orig_write = agent.write_file_atomically
    def mock_write_file_atomically(file_path, content, *args, **kwargs):
        # We start writing but simulate a failure
        raise IOError("Disk full or simulated write failure")
    monkeypatch.setattr(agent, "write_file_atomically", mock_write_file_atomically)
    
    with pytest.raises(IOError):
        agent.generate_daily_brief()
        
    # 3. Assert target file is unmodified
    with open(brief_path, "r", encoding="utf-8") as f:
        assert f.read() == "Original Brief Content"


# --- F5: Wellbeing Score Optimization Tests ---

@pytest.mark.parametrize("sleep, mood, water, energy, stress, has_workout, has_mindfulness, expected_score", [
    (8.0, "8/10", 2000, 8, 3, False, False, 88),  # Standard baseline
    (8.0, "10/10", 1000, 10, 1, True, True, 100),  # Bonuses + Max Clamp
    (4.0, "5/10", 0, 5, 10, False, False, 30),     # Extremely low levels
    (None, None, 0, None, None, False, False, 48), # Default fallbacks
])
def test_f5_wellbeing_score_accuracy(sleep, mood, water, energy, stress, has_workout, has_mindfulness, expected_score):
    """Verify wellbeing score calculations follow requirements formula precisely."""
    row = {
        "sleep_hours": sleep,
        "mood": mood,
        "water_ml": water,
        "energy_level": energy,
        "stress_level": stress,
        "date": "2026-06-09"
    }
    score = main.calculate_wellbeing_score(
        row,
        has_workout=has_workout,
        has_mindfulness=has_mindfulness
    )
    assert score == expected_score

def test_f5_wellbeing_queries_count(db_query_counter):
    """Verify that fetching health logs avoids N+1 query loop and executes at most 3 queries."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Seed 30 health logs, 15 fitness logs, 15 mindfulness logs
    for i in range(30):
        date_str = f"2026-06-{i+1:02d}"
        cursor.execute(
            "INSERT INTO health_logs (date, sleep_hours, mood, water_ml, energy_level, stress_level) VALUES (?, ?, ?, ?, ?, ?)",
            (date_str, 8.0, "8/10", 2000, 8, 3)
        )
        if i % 2 == 0:
            cursor.execute(
                "INSERT INTO fitness_logs (date, activity_type, duration_minutes) VALUES (?, ?, ?)",
                (date_str, "run", 30)
            )
            cursor.execute(
                "INSERT INTO mindfulness_logs (date, activity_type, duration_minutes) VALUES (?, ?, ?)",
                (date_str, "meditation", 15)
            )
    conn.commit()
    conn.close()

    db_query_counter.reset()
    
    # Request via FastAPI TestClient
    response = client.get("/api/health", headers={"X-API-Key": TEST_SECRET_API_KEY})
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["logs"]) == 30
    # Query count must be <= 3 (1 for health_logs, 1 for fitness_logs, 1 for mindfulness_logs)
    assert db_query_counter.total_queries <= 3


# --- F6: API Key Authentication Tests ---

@pytest.mark.parametrize("method, url, payload, expects_auth", [
    ("POST", "/api/accounts", {"name": "Savings Account", "type": "savings", "starting_balance": 10.0}, True),
    ("POST", "/api/tasks", {"title": "Submit tax report", "category": "general"}, True),
    ("PUT", "/api/tasks/1", {"title": "Submit tax report", "status": "completed"}, True),
    ("DELETE", "/api/accounts/1", None, True),
    ("GET", "/api/accounts", None, True),
    ("GET", "/api/health", None, True),
])
def test_f6_api_key_positive(method, url, payload, expects_auth):
    """Verify that valid API key allows access and GET endpoints bypass validation."""
    headers = {}
    if expects_auth:
        headers["X-API-Key"] = TEST_SECRET_API_KEY

    response = client.request(method, url, json=payload, headers=headers)
    assert response.status_code not in (401, 403)

@pytest.mark.parametrize("header_name, header_value, expected_status", [
    (None, None, 401),                               # Missing header
    ("X-API-Key", "", 401),                          # Empty key
    ("X-API-Key", "wrong-secret-key-xyz", 403),      # Wrong key
    ("Authorization", "Bearer " + TEST_SECRET_API_KEY, 401), # Incorrect header name
    ("X-API-Key", TEST_SECRET_API_KEY.upper(), 403), # Case sensitivity mismatch
    ("x-api-key", TEST_SECRET_API_KEY, 200),          # Case-insensitive header name (should pass auth)
])
def test_f6_api_key_negative(header_name, header_value, expected_status):
    """Verify unauthorized or invalid credentials are blocked and return 401 or 403."""
    headers = {}
    if header_name:
        headers[header_name] = header_value
        
    new_account = {"name": "Secret Account", "type": "checking"}
    response = client.post("/api/accounts", json=new_account, headers=headers)
    
    if expected_status in (401, 403):
        assert response.status_code in (401, 403)
    else:
        assert response.status_code == 200


@pytest.mark.parametrize("header_name, header_value, expected_status", [
    (None, None, 401),                               # Missing header
    ("X-API-Key", "", 401),                          # Empty key
    ("X-API-Key", "wrong-secret-key-xyz", 403),      # Wrong key
    ("Authorization", "Bearer " + TEST_SECRET_API_KEY, 401), # Incorrect header name
    ("X-API-Key", TEST_SECRET_API_KEY.upper(), 403), # Case sensitivity mismatch
    ("x-api-key", TEST_SECRET_API_KEY, 200),          # Case-insensitive header name (should pass auth)
])
def test_f6_api_key_negative_get(header_name, header_value, expected_status):
    """Verify unauthorized or invalid credentials block GET requests."""
    headers = {}
    if header_name:
        headers[header_name] = header_value
        
    response = client.get("/api/accounts", headers=headers)
    
    if expected_status in (401, 403):
        assert response.status_code in (401, 403)
    else:
        assert response.status_code == 200


# --- F7: CORS Private/Tailscale Network Policy Tests ---

@pytest.mark.parametrize("origin", [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://my-desktop.ts.net",
    "https://dashboard.tailscale.net:8080",
    "http://100.64.0.1",
    "http://100.127.255.255:5173",
])
def test_f7_cors_allowed_origins(origin):
    """Verify that localhost and private Tailscale network origins are allowed."""
    response = client.get("/api/overview", headers={"Origin": origin, "X-API-Key": TEST_SECRET_API_KEY})
    assert response.headers.get("access-control-allow-origin") == origin

@pytest.mark.parametrize("origin", [
    "http://google.com",
    "http://localhost.attacker.com",
    "http://my-desktop.ts.net.attacker.com",
    "http://100.63.255.255",
    "http://100.128.0.0",
    "http://192.168.1.1",
])
def test_f7_cors_disallowed_origins(origin):
    """Verify that external or spoofed origins are rejected."""
    response = client.get("/api/overview", headers={"Origin": origin, "X-API-Key": TEST_SECRET_API_KEY})
    assert "access-control-allow-origin" not in response.headers

def test_f7_cors_options_preflight_bypasses_auth():
    """Verify that preflight OPTIONS requests bypass authentication and return CORS headers."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-API-Key, Content-Type"
    }
    response = client.options("/api/accounts", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-headers" in response.headers
