import sqlite3
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "life_dashboard.db")
BACKUP_DIR = os.path.join(BACKEND_DIR, "backups")
BACKUP_FILE = os.path.join(BACKUP_DIR, "life_dashboard_weekly_backup.db")

def backup_database():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return
        
    try:
        # Connect to source and destination
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(BACKUP_FILE)
        
        # Perform safe online backup
        with dst_conn:
            src_conn.backup(dst_conn)
            
        dst_conn.close()
        src_conn.close()
        print(f"Weekly database backup updated successfully at: {BACKUP_FILE}")
    except Exception as e:
        print(f"Backup failed: {e}")

if __name__ == "__main__":
    backup_database()
