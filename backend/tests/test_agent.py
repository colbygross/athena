import os
import shutil
import sqlite3
import pytest
from datetime import datetime

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import agent

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_life_dashboard.db")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """
    Redirect the agent and database modules to use a separate test database.
    """
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr(agent, "LLM_ENABLED", False)
    database.init_db()
    
    yield
    
    # Cleanup test DB file
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_db_initialization():
    """Verify all expected tables are initialized."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row['name'] for row in cursor.fetchall()]
    
    expected_tables = [
        "processed_files",
        "transactions",
        "fitness_logs",
        "health_logs",
        "learning_progress",
        "job_applications",
        "habit_logs"
    ]
    
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' was not created."
        
    conn.close()

def test_mock_analysis_categories():
    """Verify that mock analysis returns the expected structure for various inputs."""
    res1 = agent.get_mock_analysis("receipt_starbucks.pdf", "/dummy/path")
    assert res1["category"] == "finances"
    assert res1["structured_data"]["amount"] == 15.50
    
    res2 = agent.get_mock_analysis("run_5k.gpx", "/dummy/path")
    assert res2["category"] == "fitness"
    assert res2["structured_data"]["activity_type"] == "run"
    
    res3 = agent.get_mock_analysis("medical_report.pdf", "/dummy/path")
    assert res3["category"] == "health"
    assert res3["structured_data"]["weight_lbs"] == 165.3

def test_agent_file_processing(monkeypatch, tmp_path):
    """Verify the file mover, Obsidian notes generator, and DB insertion."""
    # 1. Mock the inbox, vault, and storage folders using temp paths
    temp_vault = tmp_path / "obsidian_vault"
    temp_inbox = temp_vault / "Inbox"
    temp_inbox.mkdir(parents=True)
    temp_storage = tmp_path / "storage"
    temp_storage.mkdir()
    
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    monkeypatch.setattr(agent, "INBOX_DIR", str(temp_inbox))
    monkeypatch.setattr(agent, "STORAGE_DIR", str(temp_storage))
    
    # Create a mock receipt file in the temporary inbox
    mock_receipt = temp_inbox / "my_starbucks_receipt.txt"
    mock_receipt.write_text("Receipt: Starbucks, Date: 2026-05-23, Amount: $4.50")
    
    # 2. Run agent process
    processed = agent.process_inbox()
    
    # Verify that exactly one file was processed
    assert len(processed) == 1
    assert processed[0]["category"] == "finances"
    
    # Check that companion note was created in the Finances vault area
    moved_file_dir = temp_vault / "02_Areas" / "Finances"
    assert moved_file_dir.exists()
    
    # Check that the Markdown file exists in the destination
    dest_files = os.listdir(moved_file_dir)
    assert any(f.endswith(".md") for f in dest_files)
    
    # Check that original file was moved to the storage directory
    storage_files = os.listdir(temp_storage)
    assert any(f.endswith(".txt") for f in storage_files)
    
    # Check that the database contains the records
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM processed_files")
    files = cursor.fetchall()
    assert len(files) == 1
    assert files[0]["category"] == "finances"
    
    cursor.execute("SELECT * FROM transactions")
    txs = cursor.fetchall()
    assert len(txs) == 1
    assert txs[0]["amount"] == 15.50 # Mock value returned by get_mock_analysis for receipt
    assert txs[0]["account_id"] is not None
    
    # Check that account_id points to Capital One Checking
    cursor.execute("SELECT name FROM accounts WHERE id = ?", (txs[0]["account_id"],))
    acc_row = cursor.fetchone()
    assert acc_row is not None
    assert acc_row["name"] == "Capital One Checking"
    
    conn.close()

def test_resolve_account_id():
    """Verify that resolve_account_id accurately matches accounts or falls back to Capital One Checking."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Check accounts exist
    cursor.execute("SELECT id, name FROM accounts")
    acc_map = {row["name"]: row["id"] for row in cursor.fetchall()}
    assert "Capital One Checking" in acc_map
    assert "Capital One Savings" in acc_map
    assert "Cash" in acc_map
    
    # Fallback to Capital One Checking when nothing is specified
    assert agent.resolve_account_id(cursor) == acc_map["Capital One Checking"]
    
    # Matching savings keyword
    assert agent.resolve_account_id(cursor, struct={"account": "Savings"}) == acc_map["Capital One Savings"]
    assert agent.resolve_account_id(cursor, merchant="Interest Deposit into Savings") == acc_map["Capital One Savings"]
    
    # Matching cash keyword
    assert agent.resolve_account_id(cursor, struct={"account": "Cash"}) == acc_map["Cash"]
    assert agent.resolve_account_id(cursor, desc="Paid in cash at farmers market") == acc_map["Cash"]
    
    # Matching card/checking
    assert agent.resolve_account_id(cursor, struct={"account": "Visa Debit Card"}) == acc_map["Capital One Checking"]
    
    conn.close()

def test_normalize_model_name():
    assert agent.normalize_model_name("qwen2.5coder:3B") == "qwen2.5-coder:3b"
    assert agent.normalize_model_name("qwen2.5coder:3b") == "qwen2.5-coder:3b"
    assert agent.normalize_model_name("qwen2.5-coder:3b") == "qwen2.5-coder:3b"
    assert agent.normalize_model_name("") == "qwen2.5-coder:3b"

def test_parse_natural_language_transaction():
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # 1. Expense with cash
    res1 = agent.parse_natural_language_transaction(
        "Spent $14.50 at Chipotle on lunch with cash",
        current_date="2026-09-05",
        cursor=cursor
    )
    assert res1["amount"] == 14.50
    assert res1["type"] == "expense"
    assert res1["category"] == "food"
    assert "Chipotle" in res1["merchant"]
    
    cursor.execute("SELECT name FROM accounts WHERE id = ?", (res1["account_id"],))
    assert cursor.fetchone()["name"] == "Cash"

    # 2. Transfer between accounts
    res2 = agent.parse_natural_language_transaction(
        "Transferred $100 from Capital One Checking to Capital One Savings yesterday",
        current_date="2026-09-05",
        cursor=cursor
    )
    assert res2["amount"] == 100.0
    assert res2["type"] == "transfer"
    assert res2["date"] == "2026-09-04"
    assert res2["account_id"] is not None
    assert res2["transfer_account_id"] is not None
    assert res2["account_id"] != res2["transfer_account_id"]

    conn.close()


def test_cleanup_old_completed_tasks(monkeypatch, tmp_path):
    """Verify that completed tasks older than 3 days are preserved if in human-authored files, but deleted if DB-only or tasks.md."""
    # 1. Setup temp vault and monkeypatch path
    temp_vault = tmp_path / "obsidian_vault"
    temp_vault.mkdir(parents=True)
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    monkeypatch.setattr(agent, "WORKSPACE_DIR", str(tmp_path))
    
    # 2. Create a dummy project file with tasks
    project_file_rel = "01_Projects/Test_Project.md"
    project_file_path = temp_vault / project_file_rel
    project_file_path.parent.mkdir(parents=True, exist_ok=True)
    project_file_path.write_text(
        "# Test Project\n\n"
        "## Tasks\n"
        "- [x] Old task completed\n"
        "- [x] Recent task completed\n"
        "- [ ] Pending task\n"
    )
    
    # 3. Seed tasks in database
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Old task in human-authored file (should be preserved)
    cursor.execute(
        "INSERT INTO tasks (title, status, completed_at, source_file, line_number) VALUES (?, ?, ?, ?, ?)",
        ("Old task completed", "completed", "2026-06-03 12:00:00", project_file_rel, 4)
    )
    
    # Old task in tasks.md (should be cleaned up from DB)
    cursor.execute(
        "INSERT INTO tasks (title, status, completed_at, source_file, line_number) VALUES (?, ?, ?, ?, ?)",
        ("Old tasks.md task", "completed", "2026-06-03 12:00:00", "tasks.md", 10)
    )
    
    # Recent task (completed 1 day ago, should be preserved)
    cursor.execute(
        "INSERT INTO tasks (title, status, completed_at, source_file, line_number) VALUES (?, ?, ?, ?, ?)",
        ("Recent task completed", "completed", "2026-06-06 12:00:00", project_file_rel, 5)
    )
    
    # Pending task (not completed, should be preserved)
    cursor.execute(
        "INSERT INTO tasks (title, status, source_file, line_number) VALUES (?, ?, ?, ?)",
        ("Pending task", "pending", project_file_rel, 6)
    )
    conn.commit()
    conn.close()
    
    # 4. Run cleanup
    agent.cleanup_old_completed_tasks(days=3)
    
    # 5. Assert database state
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT title FROM tasks ORDER BY title")
    remaining_db_titles = [row['title'] for row in cursor.fetchall()]
    
    # "Old task completed" should remain in DB (preserved)
    assert "Old task completed" in remaining_db_titles
    # "Old tasks.md task" should be deleted
    assert "Old tasks.md task" not in remaining_db_titles
    # Others should remain
    assert "Recent task completed" in remaining_db_titles
    assert "Pending task" in remaining_db_titles
    conn.close()
    
    # 6. Assert file state: human-authored file should NOT have any task text deleted
    file_content = project_file_path.read_text()
    assert "- [x] Old task completed" in file_content
    assert "- [x] Recent task completed" in file_content
    assert "- [ ] Pending task" in file_content


def test_parse_workout_regimen(monkeypatch, tmp_path):
    """Verify that parsing Workout_Regimen.md returns the correct day's exercises."""
    # 1. Setup temp vault path
    temp_vault = tmp_path / "obsidian_vault"
    temp_vault.mkdir(parents=True)
    monkeypatch.setattr(agent, "VAULT_DIR", str(temp_vault))
    
    # 2. Write dummy Workout_Regimen.md
    regimen_rel = "02_Areas/Fitness/Workout_Regimen.md"
    regimen_path = temp_vault / regimen_rel
    regimen_path.parent.mkdir(parents=True, exist_ok=True)
    regimen_path.write_text(
        "---\n"
        "type: fitness-regimen\n"
        "---\n\n"
        "# Workout Regimen\n\n"
        "## 📅 Rotation Schedule\n\n"
        "- **Day 1**: Upper Strength\n"
        "- **Day 2**: Lower Strength\n"
        "- **Day 3**: Cardio\n"
        "- **Day 4**: Rest\n\n"
        "---\n\n"
        "## 🏋️ Routine Details\n\n"
        "### Day 1: Upper Strength\n"
        "1. Bench Press\n"
        "2. Rows\n\n"
        "### Day 2: Lower Strength\n"
        "1. Squats\n"
        "2. Deadlifts\n\n"
        "### Day 3: Cardio\n"
        "- Running\n"
    )
    
    # 3. Test parsing Day 2
    res = agent.parse_workout_regimen(str(temp_vault), 1) # cycle_day 1 corresponds to Day 2
    assert res is not None
    assert res["name"] == "Day 2: Lower Strength"
    assert res["exercises"] == ["Squats", "Deadlifts"]
    
    # 4. Test parsing Day 3
    res_cardio = agent.parse_workout_regimen(str(temp_vault), 2) # cycle_day 2 corresponds to Day 3
    assert res_cardio is not None
    assert res_cardio["name"] == "Day 3: Cardio"
    assert res_cardio["exercises"] == ["Running"]


