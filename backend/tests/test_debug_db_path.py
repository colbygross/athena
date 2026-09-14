import os
import sys
import pytest

# Ensure backend is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import database
import agent

def test_debug_print():
    print("\n--- DEBUG START ---")
    print("database.DB_PATH is:", database.DB_PATH)
    print("agent.get_db_connection is from:", agent.get_db_connection.__module__)
    
    conn = database.get_db_connection()
    print("database.get_db_connection() returns connection to:", conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables in database:", [r[0] for r in cursor.fetchall()])
    conn.close()
    print("--- DEBUG END ---\n")
