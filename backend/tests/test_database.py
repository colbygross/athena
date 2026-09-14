import pytest
import os
import sys
import sqlite3

# Add backend directory to sys.path to ensure database import works
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import database

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "test_db_integrity.db")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """
    Ensure the test database is re-initialized for each test.
    """
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    database.init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_foreign_keys_pragma_enabled():
    """Verify that PRAGMA foreign_keys is set to 1 (enabled) on connection."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    val = cursor.fetchone()[0]
    conn.close()
    assert val == 1

def test_foreign_key_constraints_enforced():
    """Verify that foreign key constraints are enforced and trigger IntegrityError."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Attempting to insert a transaction referencing a non-existent account ID
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO transactions (date, amount, type, category, account_id) VALUES (?, ?, ?, ?, ?);",
            ("2026-06-09", 10.0, "expense", "food", 99999)
        )
        conn.commit()
        
    # 2. Attempting to insert a recurring transaction referencing a non-existent account ID
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO recurring_transactions (name, amount, interval, category, account_id, next_due_date) VALUES (?, ?, ?, ?, ?, ?);",
            ("Netflix", 15.0, "monthly", "subscription", 99999, "2026-07-01")
        )
        conn.commit()
    conn.close()

def test_cascade_rules():
    """Verify that deleting an account triggers CASCADE rules (SET NULL or DELETE)."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Insert an account
    cursor.execute("INSERT INTO accounts (name, type, starting_balance) VALUES (?, ?, ?);", ("Test Account", "checking", 100.0))
    account_id = cursor.lastrowid
    
    # Insert a linked transaction
    cursor.execute(
        "INSERT INTO transactions (date, amount, type, category, account_id) VALUES (?, ?, ?, ?, ?);",
        ("2026-06-09", 50.0, "expense", "food", account_id)
    )
    tx_id = cursor.lastrowid
    
    # Insert a linked recurring transaction
    cursor.execute(
        "INSERT INTO recurring_transactions (name, amount, interval, category, account_id, next_due_date) VALUES (?, ?, ?, ?, ?, ?);",
        ("Test Recurring", 10.0, "monthly", "general", account_id, "2026-07-01")
    )
    rec_id = cursor.lastrowid
    
    conn.commit()
    
    # Verify linkage
    cursor.execute("SELECT account_id FROM transactions WHERE id = ?;", (tx_id,))
    assert cursor.fetchone()[0] == account_id
    
    cursor.execute("SELECT account_id FROM recurring_transactions WHERE id = ?;", (rec_id,))
    assert cursor.fetchone()[0] == account_id
    
    # Delete the account
    cursor.execute("DELETE FROM accounts WHERE id = ?;", (account_id,))
    conn.commit()
    
    # Verify transactions.account_id is SET NULL
    cursor.execute("SELECT account_id FROM transactions WHERE id = ?;", (tx_id,))
    assert cursor.fetchone()[0] is None
    
    # Verify recurring_transactions is DELETED (CASCADE)
    cursor.execute("SELECT COUNT(*) FROM recurring_transactions WHERE id = ?;", (rec_id,))
    assert cursor.fetchone()[0] == 0
    
    conn.close()

def test_explicit_indexes_exist():
    """Verify that the explicit indexes are visible in sqlite_master catalog."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index';")
    indexes = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    expected_indexes = [
        "idx_transactions_date",
        "idx_transactions_account_id",
        "idx_transactions_transfer_account_id",
        "idx_fitness_logs_date",
        "idx_learning_progress_date",
        "idx_meal_logs_date",
        "idx_mindfulness_logs_date",
        "idx_job_applications_date_applied",
        "idx_job_applications_status",
        "idx_tasks_status_due_date",
        "idx_tasks_status_completed_at",
        "idx_recurring_transactions_account_id",
        "idx_calendar_events_start_time"
    ]
    
    for idx in expected_indexes:
        assert idx in indexes, f"Index {idx} not found in sqlite_master catalog"
