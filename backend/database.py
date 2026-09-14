import sqlite3
import os

from contextvars import ContextVar

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "life_dashboard.db"))

class ManagedConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_request_scoped = False

    def close(self):
        if self._is_request_scoped:
            pass
        else:
            super().close()

    def _force_close(self):
        super().close()

_db_conn_var: ContextVar[sqlite3.Connection] = ContextVar("db_conn")

def create_new_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def get_db_connection():
    try:
        return _db_conn_var.get()
    except LookupError:
        return create_new_connection()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. processed_files table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT NOT NULL,
        new_path TEXT NOT NULL,
        category TEXT NOT NULL, -- 'finances', 'health', 'fitness', 'learning', 'career', 'general'
        description TEXT,
        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 1.5. accounts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        type TEXT CHECK(type IN ('checking', 'savings', 'credit_card', 'investment', 'cash')) NOT NULL,
        starting_balance REAL DEFAULT 0.0
    );
    """)

    # 1.6. budgets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL UNIQUE,
        limit_amount REAL NOT NULL
    );
    """)

    # 1.7. recurring_transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recurring_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        interval TEXT CHECK(interval IN ('weekly', 'monthly', 'yearly')) NOT NULL,
        category TEXT NOT NULL,
        account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
        next_due_date TEXT NOT NULL, -- YYYY-MM-DD
        active INTEGER DEFAULT 1 -- 0 or 1
    );
    """)

    # 1.8. student_loans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        type TEXT CHECK(type IN ('subsidized', 'unsubsidized')) NOT NULL,
        balance REAL NOT NULL DEFAULT 0.0,
        interest_rate REAL NOT NULL DEFAULT 0.0,
        interest_accumulated REAL NOT NULL DEFAULT 0.0
    );
    """)
    
    # 2. transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        amount REAL NOT NULL,
        type TEXT CHECK(type IN ('income', 'expense', 'transfer')) NOT NULL,
        category TEXT NOT NULL, -- e.g., food, utilities, subscription, academic, salary, transfer
        merchant TEXT,
        description TEXT,
        file_id INTEGER REFERENCES processed_files(id) ON DELETE SET NULL,
        account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
        transfer_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL
    );
    """)
    
    # 3. fitness_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fitness_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        activity_type TEXT NOT NULL, -- e.g., run, lift, cycle, swim, yoga
        duration_minutes INTEGER,
        distance_km REAL,
        calories_burned INTEGER,
        intensity TEXT CHECK(intensity IN ('low', 'medium', 'high')),
        notes TEXT,
        file_id INTEGER REFERENCES processed_files(id) ON DELETE SET NULL
    );
    """)
    
    # 4. health_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE, -- YYYY-MM-DD
        weight_lbs REAL,
        sleep_hours REAL,
        mood TEXT, -- mood scale 1-10 or description
        systolic INTEGER,
        diastolic INTEGER,
        notes TEXT
    );
    """)
    
    # 4.5. meal_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meal_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        meal_type TEXT CHECK(meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')) NOT NULL,
        description TEXT NOT NULL,
        calories INTEGER,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL
    );
    """)

    # 4.6. mindfulness_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mindfulness_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        activity_type TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        notes TEXT
    );
    """)
    
    # 5. learning_progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learning_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        topic TEXT NOT NULL, -- e.g., "React Hooks", "B-Trees"
        category TEXT NOT NULL, -- e.g., "Computer Science", "Finance", "General"
        hours_spent REAL,
        notes TEXT,
        source_link TEXT, -- GitHub commit, URL, or article title
        status TEXT CHECK(status IN ('in-progress', 'completed')) DEFAULT 'completed',
        file_id INTEGER REFERENCES processed_files(id) ON DELETE SET NULL
    );
    """)
    
    # 5.5. career_search_profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS career_search_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        resume_path TEXT,
        keywords TEXT NOT NULL,
        locations TEXT NOT NULL,
        active INTEGER DEFAULT 1
    );
    """)

    # 5.6. job_leads table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_found TEXT NOT NULL,
        company TEXT NOT NULL,
        role TEXT NOT NULL,
        location TEXT,
        salary_range TEXT,
        job_description TEXT,
        job_url TEXT UNIQUE NOT NULL,
        source TEXT NOT NULL,
        status TEXT CHECK(status IN ('lead', 'ignored', 'applied')) DEFAULT 'lead',
        profile_id INTEGER REFERENCES career_search_profiles(id) ON DELETE CASCADE
    );
    """)
    
    # 6. job_applications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_applied TEXT NOT NULL, -- YYYY-MM-DD
        company TEXT NOT NULL,
        role TEXT NOT NULL,
        salary_range TEXT,
        status TEXT CHECK(status IN ('applied', 'interviewing', 'offered', 'rejected', 'withdrawn')) DEFAULT 'applied',
        job_description_url TEXT,
        notes TEXT,
        resume_file_id INTEGER REFERENCES processed_files(id) ON DELETE SET NULL,
        lead_id INTEGER REFERENCES job_leads(id) ON DELETE SET NULL,
        recruiter_name TEXT,
        recruiter_email TEXT,
        cold_email_draft TEXT,
        outreach_status TEXT CHECK(outreach_status IN ('pending', 'sent', 'replied', 'failed')) DEFAULT 'pending',
        tailored_bullets TEXT,
        cover_letter TEXT
    );
    """)
    
    # 7. habit_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        habit_name TEXT NOT NULL, -- e.g., "Code 1 Hour", "Read 10 pages", "Workout"
        completed INTEGER DEFAULT 0, -- 0 or 1
        notes TEXT,
        UNIQUE(date, habit_name)
    );
    """)
    
    # 8. tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'general', -- 'finances', 'health', 'learning', 'career', 'general'
        status TEXT CHECK(status IN ('pending', 'completed')) DEFAULT 'pending',
        due_date TEXT, -- YYYY-MM-DD
        completed_at DATETIME,
        source_file TEXT, -- e.g., "01_Projects/My Project.md"
        line_number INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 9. calendar_events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        source TEXT CHECK(source IN ('google', 'local_ics')) DEFAULT 'local_ics',
        event_uid TEXT UNIQUE, -- Google Event ID or ICS UID
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # MIGRATION: Add account_id to transactions if it doesn't exist
    cursor.execute("PRAGMA table_info(transactions);")
    columns = [row['name'] for row in cursor.fetchall()]
    if 'account_id' not in columns:
        print("Migrating: Adding account_id column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL;")
        
    # SEEDING / ENSURING ACCOUNTS: Capital One Checking, Capital One Savings, Cash
    default_accounts = [
        ('Capital One Checking', 'checking', 0.0),
        ('Capital One Savings', 'savings', 0.0),
        ('Cash', 'cash', 0.0)
    ]
    for acc_name, acc_type, starting_bal in default_accounts:
        cursor.execute("SELECT id FROM accounts WHERE name = ?;", (acc_name,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO accounts (name, type, starting_balance) VALUES (?, ?, ?);",
                (acc_name, acc_type, starting_bal)
            )

    # Resolve Capital One Checking ID for migrations and defaults
    cursor.execute("SELECT id FROM accounts WHERE name = 'Capital One Checking';")
    cap_one_checking = cursor.fetchone()
    cap_one_checking_id = cap_one_checking['id'] if cap_one_checking else None

    # MIGRATION: If 'NF Checking' exists, migrate references to 'Capital One Checking' and remove 'NF Checking'
    cursor.execute("SELECT id FROM accounts WHERE name = 'NF Checking';")
    nf_row = cursor.fetchone()
    if nf_row and cap_one_checking_id:
        nf_id = nf_row['id']
        print(f"Migrating: Moving all records from 'NF Checking' (id={nf_id}) to 'Capital One Checking' (id={cap_one_checking_id})...")
        cursor.execute("UPDATE transactions SET account_id = ? WHERE account_id = ?;", (cap_one_checking_id, nf_id))
        cursor.execute("UPDATE transactions SET transfer_account_id = ? WHERE transfer_account_id = ?;", (cap_one_checking_id, nf_id))
        cursor.execute("UPDATE recurring_transactions SET account_id = ? WHERE account_id = ?;", (cap_one_checking_id, nf_id))
        cursor.execute("DELETE FROM accounts WHERE id = ?;", (nf_id,))

    # MIGRATION: Link existing transactions without an account to Capital One Checking (or Checking fallback)
    if cap_one_checking_id:
        cursor.execute("UPDATE transactions SET account_id = ? WHERE account_id IS NULL;", (cap_one_checking_id,))
    else:
        cursor.execute("SELECT id FROM accounts WHERE name = 'Checking';")
        checking_row = cursor.fetchone()
        if checking_row:
            cursor.execute("UPDATE transactions SET account_id = ? WHERE account_id IS NULL;", (checking_row['id'],))
        
    # MIGRATION: Add water_ml, energy_level, and stress_level to health_logs if they don't exist
    cursor.execute("PRAGMA table_info(health_logs);")
    health_columns = [row['name'] for row in cursor.fetchall()]
    if 'water_ml' not in health_columns:
        print("Migrating: Adding water_ml column to health_logs table...")
        cursor.execute("ALTER TABLE health_logs ADD COLUMN water_ml INTEGER DEFAULT 0;")
    if 'energy_level' not in health_columns:
        print("Migrating: Adding energy_level column to health_logs table...")
        cursor.execute("ALTER TABLE health_logs ADD COLUMN energy_level INTEGER;")
    if 'stress_level' not in health_columns:
        print("Migrating: Adding stress_level column to health_logs table...")
        cursor.execute("ALTER TABLE health_logs ADD COLUMN stress_level INTEGER;")
    
    # MIGRATION: Rename weight_kg to weight_lbs if it exists, and convert values
    
    # MIGRATION: Support 'transfer' transaction type and 'transfer_account_id'
    cursor.execute("PRAGMA table_info(transactions);")
    columns = [row['name'] for row in cursor.fetchall()]
    if 'transfer_account_id' not in columns:
        print("Migrating: Upgrading transactions table to support transfers...")
        
        # Disable foreign keys temporarily
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        # 1. Rename old table
        cursor.execute("ALTER TABLE transactions RENAME TO transactions_old;")
        
        # 2. Create new table
        cursor.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT CHECK(type IN ('income', 'expense', 'transfer')) NOT NULL,
            category TEXT NOT NULL,
            merchant TEXT,
            description TEXT,
            file_id INTEGER REFERENCES processed_files(id) ON DELETE SET NULL,
            account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            transfer_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL
        );
        """)
        
        # 3. Copy data
        cursor.execute("""
        INSERT INTO transactions (id, date, amount, type, category, merchant, description, file_id, account_id)
        SELECT id, date, amount, type, category, merchant, description, file_id, account_id
        FROM transactions_old;
        """)
        
        # 4. Drop old table
        cursor.execute("DROP TABLE transactions_old;")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON;")

        # 5. Fix existing transfers (transactions 4 and 5)
        # Dynamic resolution: find matching transfer transactions (expense and income with category 'transfer' and amount 120.0 on same day)
        cursor.execute("""
            SELECT id, date, amount, account_id FROM transactions 
            WHERE category = 'transfer' AND type = 'expense' AND amount = 120.0 LIMIT 1;
        """)
        expense_tx = cursor.fetchone()
        if expense_tx:
            cursor.execute("""
                SELECT id, account_id FROM transactions 
                WHERE category = 'transfer' AND type = 'income' AND amount = ? AND date = ? LIMIT 1;
            """, (expense_tx['amount'], expense_tx['date']))
            income_tx = cursor.fetchone()
            if income_tx:
                cursor.execute("""
                    UPDATE transactions SET type = 'transfer', transfer_account_id = ? WHERE id = ?;
                """, (income_tx['account_id'], expense_tx['id']))
                cursor.execute("DELETE FROM transactions WHERE id = ?;", (income_tx['id'],))
    if 'weight_kg' in health_columns:
        print("Migrating: Renaming weight_kg to weight_lbs and converting values...")
        try:
            cursor.execute("ALTER TABLE health_logs RENAME COLUMN weight_kg TO weight_lbs;")
            cursor.execute("UPDATE health_logs SET weight_lbs = ROUND(weight_lbs * 2.20462, 1) WHERE weight_lbs IS NOT NULL;")
            print("Successfully migrated weight_kg to weight_lbs and converted weights to lbs.")
        except Exception as e:
            print(f"Error during weight_lbs migration: {e}")
    
    # MIGRATION: Add priority and importance to tasks if they don't exist
    cursor.execute("PRAGMA table_info(tasks);")
    task_columns = [row['name'] for row in cursor.fetchall()]
    if 'priority' not in task_columns:
        print("Migrating: Adding priority column to tasks table...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'medium';")
    if 'importance' not in task_columns:
        print("Migrating: Adding importance column to tasks table...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN importance TEXT DEFAULT 'minor';")
    
    # MIGRATION: Add career columns to job_applications if they don't exist
    cursor.execute("PRAGMA table_info(job_applications);")
    job_app_columns = [row['name'] for row in cursor.fetchall()]
    if 'lead_id' not in job_app_columns:
        print("Migrating: Adding lead_id column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN lead_id INTEGER REFERENCES job_leads(id) ON DELETE SET NULL;")
    if 'recruiter_name' not in job_app_columns:
        print("Migrating: Adding recruiter_name column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN recruiter_name TEXT;")
    if 'recruiter_email' not in job_app_columns:
        print("Migrating: Adding recruiter_email column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN recruiter_email TEXT;")
    if 'cold_email_draft' not in job_app_columns:
        print("Migrating: Adding cold_email_draft column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN cold_email_draft TEXT;")
    if 'outreach_status' not in job_app_columns:
        print("Migrating: Adding outreach_status column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN outreach_status TEXT CHECK(outreach_status IN ('pending', 'sent', 'replied', 'failed')) DEFAULT 'pending';")
    if 'tailored_bullets' not in job_app_columns:
        print("Migrating: Adding tailored_bullets column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN tailored_bullets TEXT;")
    if 'cover_letter' not in job_app_columns:
        print("Migrating: Adding cover_letter column to job_applications table...")
        cursor.execute("ALTER TABLE job_applications ADD COLUMN cover_letter TEXT;")
    
    # MIGRATION: Remove source CHECK constraint on job_leads if present
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='job_leads';")
    row = cursor.fetchone()
    if row and row['sql'] and "source IN (" in row['sql']:
        print("Migrating: Removing source CHECK constraint on job_leads table...")
        cursor.execute("PRAGMA foreign_keys=OFF;")
        cursor.execute("ALTER TABLE job_leads RENAME TO job_leads_old;")
        cursor.execute("""
        CREATE TABLE job_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_found TEXT NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT,
            salary_range TEXT,
            job_description TEXT,
            job_url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            status TEXT CHECK(status IN ('lead', 'ignored', 'applied')) DEFAULT 'lead',
            profile_id INTEGER REFERENCES career_search_profiles(id) ON DELETE CASCADE,
            is_remote INTEGER DEFAULT 0,
            tier INTEGER DEFAULT 1,
            match_score INTEGER DEFAULT 0
        );
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO job_leads (id, date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
            SELECT id, date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id
            FROM job_leads_old;
        """)
        cursor.execute("DROP TABLE job_leads_old;")
        cursor.execute("PRAGMA foreign_keys=ON;")

    # MIGRATION: Add is_remote, tier, and match_score to job_leads if they don't exist
    cursor.execute("PRAGMA table_info(job_leads);")
    job_lead_columns = [row['name'] for row in cursor.fetchall()]
    if 'is_remote' not in job_lead_columns:
        print("Migrating: Adding is_remote column to job_leads table...")
        cursor.execute("ALTER TABLE job_leads ADD COLUMN is_remote INTEGER DEFAULT 0;")
    if 'tier' not in job_lead_columns:
        print("Migrating: Adding tier column to job_leads table...")
        cursor.execute("ALTER TABLE job_leads ADD COLUMN tier INTEGER DEFAULT 1;")
    if 'match_score' not in job_lead_columns:
        print("Migrating: Adding match_score column to job_leads table...")
        cursor.execute("ALTER TABLE job_leads ADD COLUMN match_score INTEGER DEFAULT 0;")

    # 6.5. outreach_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outreach_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER REFERENCES job_applications(id) ON DELETE CASCADE,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'success'
    );
    """)

    # Create explicit indexes for performance optimization
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_transfer_account_id ON transactions(transfer_account_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fitness_logs_date ON fitness_logs(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_progress_date ON learning_progress(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_meal_logs_date ON meal_logs(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mindfulness_logs_date ON mindfulness_logs(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_applications_date_applied ON job_applications(date_applied);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_due_date ON tasks(status, due_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_completed_at ON tasks(status, completed_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recurring_transactions_account_id ON recurring_transactions(account_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_source_file ON tasks(source_file);")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
