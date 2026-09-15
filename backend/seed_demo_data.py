#!/usr/bin/env python3
"""
ATHENA - Synthetic Telemetry Data Seeder
Populates SQLite with realistic, anonymous demonstration telemetry:
- Financial accounts, budgets, recurring bills, and ledger transactions
- Daily health vitals, fitness workouts, meal logs, and mindfulness logs
- Master task checklist items and recurring micro-habits
- Academic/CS learning progress ledger
- Career discovery leads and job application pipelines
- Calendar schedule events
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta, date
import random

# Ensure backend directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import database

def seed_telemetry(db_path: str = None):
    if db_path:
        database.DB_PATH = db_path

    print(f"[*] Initializing database schema at: {database.DB_PATH}")
    database.init_db()

    conn = database.create_new_connection()
    cursor = conn.cursor()

    today = date.today()

    print("[*] Seeding Financial Accounts & Ledgers...")
    # Accounts
    accounts_data = [
        ("Primary Checking", "checking", 3450.00),
        ("High-Yield Savings", "savings", 12850.50),
        ("Sapphire Rewards Card", "credit_card", -420.75),
        ("Emergency Reserves", "savings", 8500.00),
        ("Tactical Cash", "cash", 180.00)
    ]
    account_ids = {}
    for name, acct_type, bal in accounts_data:
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            account_ids[name] = row["id"]
        else:
            cursor.execute(
                "INSERT INTO accounts (name, type, starting_balance) VALUES (?, ?, ?)",
                (name, acct_type, bal)
            )
            account_ids[name] = cursor.lastrowid

    # Budgets
    budgets_data = [
        ("food", 550.00),
        ("groceries", 400.00),
        ("utilities", 220.00),
        ("cloud_infra", 85.00),
        ("fitness", 110.00),
        ("learning", 75.00)
    ]
    for cat, limit in budgets_data:
        cursor.execute(
            "INSERT OR IGNORE INTO budgets (category, limit_amount) VALUES (?, ?)",
            (cat, limit)
        )

    # Recurring Transactions
    recurring_data = [
        ("Cloud Server Hosting (VPS)", 48.00, "monthly", "cloud_infra", account_ids["Primary Checking"], (today + timedelta(days=12)).isoformat(), 1),
        ("Fiber Broadband Internet", 79.99, "monthly", "utilities", account_ids["Primary Checking"], (today + timedelta(days=5)).isoformat(), 1),
        ("Gym & Bouldering Membership", 85.00, "monthly", "fitness", account_ids["Primary Checking"], (today + timedelta(days=18)).isoformat(), 1),
        ("Music Streaming Premium", 11.99, "monthly", "entertainment", account_ids["Sapphire Rewards Card"], (today + timedelta(days=9)).isoformat(), 1)
    ]
    for rec in recurring_data:
        cursor.execute("""
            INSERT OR IGNORE INTO recurring_transactions 
            (name, amount, interval, category, account_id, next_due_date, active) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rec)

    # Transactions (Past 30 days)
    sample_merchants = [
        ("Whole Foods Market", "groceries", 64.20, "Weekly organic groceries"),
        ("Trader Joe's", "groceries", 42.15, "Pantry essentials and greens"),
        ("Local Espresso Lab", "food", 5.75, "Cold brew & oat cortado"),
        ("AWS Web Services", "cloud_infra", 32.10, "Container cluster & S3 backup"),
        ("DigitalOcean", "cloud_infra", 14.00, "Staging Droplet & DNS routing"),
        ("REI Co-op", "fitness", 54.00, "Chalk & climbing gear replenishment"),
        ("Steam Games", "entertainment", 29.99, "Indie tactical roguelike"),
        ("GitHub Copilot / API", "learning", 20.00, "Developer productivity subscription")
    ]

    for i in range(25):
        txn_date = today - timedelta(days=random.randint(0, 28))
        merchant, cat, base_amt, desc = random.choice(sample_merchants)
        amt = round(base_amt + random.uniform(-3.5, 6.0), 2)
        acct_id = account_ids["Primary Checking"] if random.random() > 0.3 else account_ids["Sapphire Rewards Card"]
        cursor.execute("""
            INSERT INTO transactions (date, amount, type, category, merchant, description, account_id)
            VALUES (?, ?, 'expense', ?, ?, ?, ?)
        """, (txn_date.isoformat(), amt, cat, merchant, desc, acct_id))

    # Bi-weekly direct deposit income
    for offset in [2, 16, 30]:
        income_date = today - timedelta(days=offset)
        cursor.execute("""
            INSERT INTO transactions (date, amount, type, category, merchant, description, account_id)
            VALUES (?, 3250.00, 'income', 'salary', 'Engineering Payroll', 'Direct Deposit Payroll', ?)
        """, (income_date.isoformat(), account_ids["Primary Checking"]))

    print("[*] Seeding Health & Vitals Telemetry...")
    # Health Logs (30 days)
    for i in range(30):
        log_date = today - timedelta(days=i)
        weight = round(168.5 + random.uniform(-1.2, 1.2), 1)
        sleep = round(random.uniform(7.0, 8.5), 1)
        systolic = random.randint(114, 122)
        diastolic = random.randint(74, 80)
        moods = ["Energetic / Focused", "Balanced", "Clear Minded", "High Focus", "Calm"]
        cursor.execute("""
            INSERT OR IGNORE INTO health_logs (date, weight_lbs, sleep_hours, mood, systolic, diastolic, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (log_date.isoformat(), weight, sleep, random.choice(moods), systolic, diastolic, "Resting telemetry nominal."))

    print("[*] Seeding Fitness Workouts...")
    # Fitness Logs
    activities = [
        ("Trail Run", 38, 6.5, 420, "high", "Zone 2 aerobic base pacing"),
        ("Barbell Strength", 55, None, 380, "high", "Deadlifts 4x5, Overhead Press 4x6, Core"),
        ("Zone 2 Cycling", 45, 18.2, 360, "medium", "Indoor steady cadence session"),
        ("Bouldering / Climbing", 60, None, 410, "high", "V5 project sends and grip endurance"),
        ("Restorative Yoga", 30, None, 140, "low", "Hip mobility and posterior chain stretches")
    ]
    for i in range(16):
        workout_date = today - timedelta(days=i * 2)
        act, dur, dist, cals, intensity, notes = random.choice(activities)
        cursor.execute("""
            INSERT INTO fitness_logs (date, activity_type, duration_minutes, distance_km, calories_burned, intensity, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (workout_date.isoformat(), act, dur, dist, cals, intensity, notes))

    print("[*] Seeding Habit Tracker Records...")
    # Habit Logs (Last 14 days)
    core_habits = [
        "Morning Sunlight & Hydration",
        "Deep Work Sprint (90m)",
        "Daily Physical Training",
        "Technical Reading & CS Drill",
        "Zero Processed Sugar"
    ]
    for day_offset in range(14):
        habit_date = today - timedelta(days=day_offset)
        for h in core_habits:
            completed = 1 if random.random() > 0.15 else 0
            cursor.execute("""
                INSERT OR IGNORE INTO habit_logs (date, habit_name, completed, notes)
                VALUES (?, ?, ?, ?)
            """, (habit_date.isoformat(), h, completed, "Tracked via Athena CLI"))

    print("[*] Seeding Master Tasks...")
    # Tasks
    tasks_data = [
        ("Review pull request on FastAPI telemetry streaming", "learning", "pending", (today + timedelta(days=1)).isoformat(), "high"),
        ("Benchmark SQLite WAL performance under concurrent async reads", "learning", "completed", (today - timedelta(days=2)).isoformat(), "high"),
        ("Prepare presentation deck for Applied AI architecture review", "career", "pending", (today + timedelta(days=3)).isoformat(), "high"),
        ("Rebalance index fund portfolio allocations", "finances", "pending", (today + timedelta(days=7)).isoformat(), "medium"),
        ("Tune Qwen-VL prompt temperature for receipt JSON parsing", "learning", "completed", (today - timedelta(days=5)).isoformat(), "medium"),
        ("Restock electrolyte powder and creatine monohydrate", "health", "completed", (today - timedelta(days=1)).isoformat(), "low"),
        ("Calibrate optical heart-rate strap telemetry", "fitness", "pending", (today + timedelta(days=4)).isoformat(), "low")
    ]
    for title, cat, status, due, priority in tasks_data:
        comp_at = datetime.now().isoformat() if status == "completed" else None
        cursor.execute("""
            INSERT INTO tasks (title, category, status, due_date, completed_at, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, cat, status, due, comp_at, priority))

    print("[*] Seeding Technical Learning Progress...")
    # Learning logs
    learning_topics = [
        ("SQLite WAL & Pragma Concurrency", "Computer Science", 3.0, "Analyzed lock escalation, checkpoint algorithms, and busy timeout handlers under async workloads.", "https://sqlite.org/wal.html"),
        ("Multi-Modal LLM Vision Ingestion", "Artificial Intelligence", 4.5, "Integrated Ollama Qwen-VL for high-fidelity OCR and structured JSON extraction from invoices.", "https://github.com/ollama/ollama"),
        ("Vite React Micro-Frontends & HMR", "Frontend Engineering", 2.5, "Optimized tailwind typography bundling and virtualized large telemetry tables.", "https://vitejs.dev"),
        ("Linux Systemd & Containerization Isolation", "DevOps", 3.0, "Constructed hardened multi-stage Docker build with non-root security context.", "https://docs.docker.com")
    ]
    for topic, cat, hours, notes, url in learning_topics:
        cursor.execute("""
            INSERT INTO learning_progress (date, topic, category, hours_spent, notes, source_link, status)
            VALUES (?, ?, ?, ?, ?, ?, 'completed')
        """, ((today - timedelta(days=random.randint(1, 14))).isoformat(), topic, cat, hours, notes, url))

    print("[*] Seeding Career Pipelines & Job Leads...")
    # Job Leads & Applications
    cursor.execute("""
        INSERT OR IGNORE INTO career_search_profiles (name, keywords, locations, active)
        VALUES ('Full-Stack & Applied AI Engineer', 'Python, FastAPI, React, AI, LLM, Docker', 'Remote, Boston, Hybrid', 1)
    """)
    profile_id = cursor.lastrowid or 1

    sample_leads = [
        ("Scale AI", "Applied AI Systems Engineer", "San Francisco, CA (Remote)", "$160k - $210k", "https://scale.com/careers/sample-ai-eng"),
        ("Linear", "Full-Stack Product Engineer", "Remote", "$150k - $190k", "https://linear.app/careers/fullstack"),
        ("Modal Labs", "Distributed Systems & Cloud Engineer", "New York, NY", "$170k - $220k", "https://modal.com/careers/systems")
    ]
    for comp, role, loc, sal, url in sample_leads:
        cursor.execute("""
            INSERT OR IGNORE INTO job_leads (date_found, company, role, location, salary_range, job_url, source, status, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, 'Discovery Engine', 'lead', ?)
        """, ((today - timedelta(days=random.randint(1, 10))).isoformat(), comp, role, loc, sal, url, profile_id))

    cursor.execute("""
        INSERT INTO job_applications (date_applied, company, role, salary_range, status, job_description_url, notes)
        VALUES (?, 'Anthropic Labs', 'Full-Stack Platform Engineer', '$175,000 - $225,000', 'interviewing', 'https://anthropic.com/careers', 'Technical phone screen completed; architecture system interview scheduled.')
    """, ((today - timedelta(days=8)).isoformat(),))

    print("[*] Seeding Calendar Events...")
    # Calendar Events
    cal_events = [
        ("Technical Architecture Deep Dive", "Applied AI systems and distributed state review", today.isoformat() + " 14:00:00", today.isoformat() + " 15:30:00", "local_ics", "demo-event-1"),
        ("Tactical Aerobic Conditioning Run", "6km tempo pacing", (today + timedelta(days=1)).isoformat() + " 07:00:00", (today + timedelta(days=1)).isoformat() + " 08:00:00", "local_ics", "demo-event-2"),
        ("Weekly Retrospective & Ledger Audit", "Review category budgets and weekly milestones", (today + timedelta(days=2)).isoformat() + " 18:00:00", (today + timedelta(days=2)).isoformat() + " 19:00:00", "local_ics", "demo-event-3")
    ]
    for ev in cal_events:
        cursor.execute("""
            INSERT OR IGNORE INTO calendar_events (title, description, start_time, end_time, source, event_uid)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ev)

    conn.commit()
    conn.close()
    print("[✓] Successfully seeded ATHENA demo telemetry database!")

def seed_vault(vault_dir: str = None):
    vault = vault_dir or os.getenv("VAULT_DIR", os.path.join(os.path.dirname(CURRENT_DIR), "obsidian_vault"))
    if not os.path.exists(vault):
        return
    print(f"[*] Checking demo Obsidian vault templates in: {vault}")
    for root, _, files in os.walk(vault):
        for f in files:
            if f.endswith(".sample.md"):
                target_name = f[:-10] + ".md"
                target_path = os.path.join(root, target_name)
                src_path = os.path.join(root, f)
                if not os.path.exists(target_path):
                    import shutil
                    shutil.copy2(src_path, target_path)
                    print(f"    + Created starter note: {os.path.relpath(target_path, vault)}")

if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else None
    seed_telemetry(target_db)
    seed_vault()
