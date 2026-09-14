import os
import re
import threading
import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import ipaddress
from urllib.parse import urlparse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from icalendar import Calendar, Event

from database import get_db_connection, init_db, _db_conn_var, create_new_connection
import agent
import career_agent
import job_discovery_engine
import job_tailor_engine


# Initialize DB on startup
init_db()
try:
    agent.sync_local_ics_to_db()
except Exception as e:
    print(f"Error syncing local ICS on startup: {e}")

app = FastAPI(title="Life Organizer Dashboard API")

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    # Open request-scoped database connection
    conn = create_new_connection()
    conn._is_request_scoped = True
    token = _db_conn_var.set(conn)
    try:
        response = await call_next(request)
        return response
    finally:
        # Force close the connection
        conn._force_close()
        _db_conn_var.reset(token)

# Load API Key on startup
API_KEY = os.getenv("API_KEY")

def is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    try:
        parsed = urlparse(origin)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in ("localhost", "127.0.0.1"):
            return True
        if hostname.endswith(".ts.net") or hostname.endswith(".tailscale.net"):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            if ip in ipaddress.ip_network("100.64.0.0/10"):
                return True
        except ValueError:
            pass
    except Exception:
        pass
    return False

@app.middleware("http")
async def security_and_cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    
    # 1. Handle CORS preflight OPTIONS requests
    if request.method == "OPTIONS":
        if is_allowed_origin(origin):
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
            return Response(status_code=200, headers=headers)
        return Response(status_code=400, content="CORS Origin Not Allowed")

    # 2. Handle API Key Authentication for all incoming requests under /api
    if request.url.path.startswith("/api"):
        if API_KEY:
            provided_key = request.headers.get("x-api-key")
            if not provided_key:
                return JSONResponse(status_code=401, content={"detail": "X-API-Key header missing"})
            if provided_key != API_KEY:
                return JSONResponse(status_code=403, content={"detail": "Invalid API Key"})

    # 3. Proceed with request
    response = await call_next(request)

    # 4. Append CORS headers if origin is allowed
    if is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        
    return response

# Agent status tracking
agent_running = False
agent_lock = threading.Lock()

# Pydantic schemas for manual entries
class AccountCreate(BaseModel):
    name: str
    type: str
    starting_balance: float = 0.0

class BudgetCreate(BaseModel):
    category: str
    limit_amount: float

class RecurringCreate(BaseModel):
    name: str
    amount: float
    interval: str
    category: str
    account_id: int
    next_due_date: str

class TransactionCreate(BaseModel):
    date: str
    amount: float
    type: str
    category: str
    merchant: Optional[str] = None
    description: Optional[str] = None
    account_id: Optional[int] = None
    transfer_account_id: Optional[int] = None

class NLPTransactionRequest(BaseModel):
    text: str
    preview: Optional[bool] = False

class FitnessLogCreate(BaseModel):
    date: str
    activity_type: str
    duration_minutes: int
    distance_km: Optional[float] = None
    calories_burned: Optional[int] = None
    intensity: str
    notes: Optional[str] = None

class HealthLogCreate(BaseModel):
    date: str
    weight_lbs: Optional[float] = None
    sleep_hours: Optional[float] = None
    mood: Optional[str] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    notes: Optional[str] = None
    water_ml: Optional[int] = 0
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None

class MealLogCreate(BaseModel):
    date: str
    meal_type: str
    description: str
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

class MindfulnessLogCreate(BaseModel):
    date: str
    activity_type: str
    duration_minutes: int
    notes: Optional[str] = None

class LearningProgressCreate(BaseModel):
    date: str
    topic: str
    category: str
    hours_spent: float
    notes: Optional[str] = None
    source_link: Optional[str] = None
    status: str = "completed"

class JobApplicationCreate(BaseModel):
    date_applied: str
    company: str
    role: str
    salary_range: Optional[str] = None
    status: str = "applied"
    job_description_url: Optional[str] = None
    notes: Optional[str] = None

class JobApplicationUpdate(BaseModel):
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    cold_email_draft: Optional[str] = None
    tailored_bullets: Optional[str] = None
    cover_letter: Optional[str] = None
    status: Optional[str] = None

class CareerProfileCreate(BaseModel):
    name: str
    resume_path: Optional[str] = None
    keywords: str
    locations: str
    active: Optional[int] = 1

class JobLeadUrlIngest(BaseModel):
    url: str
    profile_id: int



class HabitLogCreate(BaseModel):
    date: str
    habit_name: str
    completed: int # 0 or 1
    notes: Optional[str] = None


class StudentLoanCreate(BaseModel):
    name: str
    type: str  # 'subsidized' or 'unsubsidized'
    balance: float = 0.0
    interest_rate: float = 0.0
    interest_accumulated: float = 0.0


class StudentLoanUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    balance: Optional[float] = None
    interest_rate: Optional[float] = None
    interest_accumulated: Optional[float] = None


@app.get("/api/overview")
def get_overview():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Total expenses this month
        current_month = datetime.now().strftime("%Y-%m")
        cursor.execute(
            "SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ?",
            (f"{current_month}%",)
        )
        monthly_expense = cursor.fetchone()[0] or 0.0
        
        # 2. Workouts count this week (last 7 days)
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT COUNT(*) FROM fitness_logs WHERE date >= ?",
            (seven_days_ago,)
        )
        weekly_workouts = cursor.fetchone()[0] or 0
        
        # 3. Learning hours this week
        cursor.execute(
            "SELECT SUM(hours_spent) FROM learning_progress WHERE date >= ?",
            (seven_days_ago,)
        )
        weekly_learning_hours = cursor.fetchone()[0] or 0.0
        
        # 4. Job applications count (active: applied or interviewing)
        cursor.execute(
            "SELECT COUNT(*) FROM job_applications WHERE status IN ('applied', 'interviewing')"
        )
        active_job_applications = cursor.fetchone()[0] or 0
        
        # 5. Recent transactions
        cursor.execute(
            "SELECT * FROM transactions ORDER BY date DESC LIMIT 5"
        )
        recent_txs = [dict(row) for row in cursor.fetchall()]
        
        # 6. Recent files processed
        cursor.execute(
            "SELECT * FROM processed_files ORDER BY processed_at DESC LIMIT 5"
        )
        recent_files = [dict(row) for row in cursor.fetchall()]
        
        # 7. Habit completion today
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT habit_name, completed FROM habit_logs WHERE date = ?",
            (today,)
        )
        todays_habits = [dict(row) for row in cursor.fetchall()]
        
        return {
            "monthly_expense": monthly_expense,
            "weekly_workouts": weekly_workouts,
            "weekly_learning_hours": weekly_learning_hours,
            "active_jobs": active_job_applications,
            "recent_transactions": recent_txs,
            "recent_files": recent_files,
            "todays_habits": todays_habits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Helper to advance recurring due dates
def advance_date(date_str, interval):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if interval == "weekly":
        next_dt = dt + timedelta(days=7)
    elif interval == "monthly":
        year = dt.year + (dt.month // 12)
        month = (dt.month % 12) + 1
        import calendar
        day = min(dt.day, calendar.monthrange(year, month)[1])
        next_dt = datetime(year, month, day)
    elif interval == "yearly":
        next_dt = datetime(dt.year + 1, dt.month, dt.day)
    else:
        next_dt = dt + timedelta(days=30)
    return next_dt.strftime("%Y-%m-%d")

# --- FINANCES ---
@app.get("/api/finances")
def get_finances(account_id: Optional[int] = None, date_range: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id"
        params = []
        where_clauses = []
        
        if account_id is not None:
            where_clauses.append("t.account_id = ?")
            params.append(account_id)
            
        if date_range is not None and date_range != "all":
            today = datetime.now()
            if date_range == "this_month":
                current_month = today.strftime("%Y-%m")
                where_clauses.append("t.date LIKE ?")
                params.append(f"{current_month}%")
            elif date_range == "last_30_days":
                thirty_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")
                where_clauses.append("t.date >= ?")
                params.append(thirty_days_ago)
            elif date_range == "last_90_days":
                ninety_days_ago = (today - timedelta(days=90)).strftime("%Y-%m-%d")
                where_clauses.append("t.date >= ?")
                params.append(ninety_days_ago)
                
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY t.date DESC"
        cursor.execute(query, tuple(params))
        txs = [dict(row) for row in cursor.fetchall()]
        
        # Category breakdown query based on same filters
        breakdown_query = "SELECT category, SUM(amount) as total FROM transactions t"
        breakdown_where = list(where_clauses)
        breakdown_where.append("t.type='expense'")
        
        breakdown_query += " WHERE " + " AND ".join(breakdown_where)
        breakdown_query += " GROUP BY category"
        
        cursor.execute(breakdown_query, tuple(params))
        breakdown = [dict(row) for row in cursor.fetchall()]
        
        # Fetch accounts with balances
        cursor.execute("""
            SELECT a.id, a.name, a.type, a.starting_balance,
                   a.starting_balance + 
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='income'), 0) -
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='expense'), 0) -
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='transfer'), 0) +
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE transfer_account_id = a.id AND type='transfer'), 0) as current_balance
            FROM accounts a
        """)
        accounts = [dict(row) for row in cursor.fetchall()]
        
        # Calculate Net Wealth
        net_wealth = 0.0
        for acc in accounts:
            if acc['type'] in ('checking', 'savings', 'investment', 'cash'):
                net_wealth += acc['current_balance']
            elif acc['type'] == 'credit_card':
                net_wealth -= acc['current_balance']
                
        # Fetch all budgets
        cursor.execute("SELECT * FROM budgets")
        budgets = [dict(row) for row in cursor.fetchall()]
        
        # Fetch active recurring transactions
        cursor.execute("""
            SELECT r.*, a.name as account_name 
            FROM recurring_transactions r 
            LEFT JOIN accounts a ON r.account_id = a.id 
            WHERE r.active = 1
            ORDER BY r.next_due_date ASC
        """)
        recurring = [dict(row) for row in cursor.fetchall()]
        
        # Fetch student loans
        cursor.execute("SELECT * FROM student_loans ORDER BY name ASC")
        student_loans = [dict(row) for row in cursor.fetchall()]
        
        return {
            "transactions": txs, 
            "breakdown": breakdown, 
            "accounts": accounts,
            "net_wealth": net_wealth,
            "budgets": budgets,
            "recurring": recurring,
            "student_loans": student_loans
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/finances")
def add_transaction(tx: TransactionCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Default to Capital One Checking account if account_id is not provided
    account_id = tx.account_id
    if not account_id:
        cursor.execute("SELECT id FROM accounts WHERE name = 'Capital One Checking';")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id FROM accounts WHERE name = 'Checking';")
            row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id FROM accounts WHERE type = 'checking' LIMIT 1;")
            row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id FROM accounts ORDER BY id ASC LIMIT 1;")
            row = cursor.fetchone()
        account_id = row['id'] if row else 1
        
    try:
        if tx.type == "transfer" and tx.transfer_account_id is None:
            raise HTTPException(status_code=400, detail="transfer_account_id is required for transfer transactions.")
            
        cursor.execute(
            "INSERT INTO transactions (date, amount, type, category, merchant, description, account_id, transfer_account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tx.date, tx.amount, tx.type, tx.category, tx.merchant, tx.description, account_id, tx.transfer_account_id)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/finances/log-nlp")
def log_transaction_nlp(req: NLPTransactionRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Transaction text is required")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        parsed = agent.parse_natural_language_transaction(req.text, cursor=cursor)
        
        if req.preview:
            return {
                "status": "preview",
                "parsed": parsed
            }
            
        if parsed["type"] == "transfer" and parsed["transfer_account_id"] is None:
            # Fallback if no destination was found
            cursor.execute("SELECT id FROM accounts WHERE id != ? ORDER BY id ASC LIMIT 1", (parsed["account_id"],))
            row = cursor.fetchone()
            if row:
                parsed["transfer_account_id"] = row["id"]
            else:
                raise HTTPException(status_code=400, detail="Transfer requires a secondary account")
                
        cursor.execute(
            "INSERT INTO transactions (date, amount, type, category, merchant, description, account_id, transfer_account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                parsed["date"],
                parsed["amount"],
                parsed["type"],
                parsed["category"],
                parsed["merchant"],
                parsed["description"],
                parsed["account_id"],
                parsed["transfer_account_id"]
            )
        )
        conn.commit()
        tx_id = cursor.lastrowid
        return {
            "status": "success",
            "id": tx_id,
            "parsed": parsed
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- ACCOUNTS ---
@app.get("/api/accounts")
def get_accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT a.id, a.name, a.type, a.starting_balance,
                   a.starting_balance + 
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='income'), 0) -
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='expense'), 0) -
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='transfer'), 0) +
                   COALESCE((SELECT SUM(amount) FROM transactions WHERE transfer_account_id = a.id AND type='transfer'), 0) as current_balance
            FROM accounts a
        """)
        return {"accounts": [dict(row) for row in cursor.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/accounts")
def add_account(acc: AccountCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (name, type, starting_balance) VALUES (?, ?, ?)",
            (acc.name, acc.type, acc.starting_balance)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Enable foreign keys for cascade and set null behavior
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Account not found")
        
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# --- STUDENT LOANS ---
@app.post("/api/student-loans")
def add_student_loan(loan: StudentLoanCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO student_loans (name, type, balance, interest_rate, interest_accumulated) VALUES (?, ?, ?, ?, ?)",
            (loan.name, loan.type, loan.balance, loan.interest_rate, loan.interest_accumulated)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Student loan with this name already exists")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/student-loans/{loan_id}")
def update_student_loan(loan_id: int, loan_data: StudentLoanUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM student_loans WHERE id = ?", (loan_id,))
        loan = cursor.fetchone()
        if not loan:
            raise HTTPException(status_code=404, detail="Student loan not found")
        
        update_fields = []
        params = []
        
        if loan_data.name is not None:
            update_fields.append("name = ?")
            params.append(loan_data.name)
        if loan_data.type is not None:
            update_fields.append("type = ?")
            params.append(loan_data.type)
        if loan_data.balance is not None:
            update_fields.append("balance = ?")
            params.append(loan_data.balance)
        if loan_data.interest_rate is not None:
            update_fields.append("interest_rate = ?")
            params.append(loan_data.interest_rate)
        if loan_data.interest_accumulated is not None:
            update_fields.append("interest_accumulated = ?")
            params.append(loan_data.interest_accumulated)
            
        if update_fields:
            query = f"UPDATE student_loans SET {', '.join(update_fields)} WHERE id = ?"
            params.append(loan_id)
            cursor.execute(query, tuple(params))
            conn.commit()
            
        return {"status": "success", "id": loan_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Student loan with this name already exists")
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/student-loans/{loan_id}")
def delete_student_loan(loan_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM student_loans WHERE id = ?", (loan_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Student loan not found")
        
        cursor.execute("DELETE FROM student_loans WHERE id = ?", (loan_id,))
        conn.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# --- BUDGETS ---
@app.get("/api/budgets")
def get_budgets():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM budgets")
        return {"budgets": [dict(row) for row in cursor.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/budgets")
def set_budget(bud: BudgetCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO budgets (category, limit_amount) VALUES (?, ?)",
            (bud.category, bud.limit_amount)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- RECURRING TRANSACTIONS ---
@app.get("/api/recurring")
def get_recurring():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.*, a.name as account_name 
            FROM recurring_transactions r 
            LEFT JOIN accounts a ON r.account_id = a.id
        """)
        return {"recurring": [dict(row) for row in cursor.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/recurring")
def add_recurring(rec: RecurringCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO recurring_transactions 
               (name, amount, interval, category, account_id, next_due_date, active) 
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (rec.name, rec.amount, rec.interval, rec.category, rec.account_id, rec.next_due_date)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/recurring/{recurring_id}/pay")
def pay_recurring(recurring_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM recurring_transactions WHERE id = ?", (recurring_id,))
        rec = cursor.fetchone()
        if not rec:
            raise HTTPException(status_code=404, detail="Recurring item not found")
            
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """INSERT INTO transactions 
               (date, amount, type, category, merchant, description, account_id) 
               VALUES (?, ?, 'expense', ?, ?, ?, ?)""",
            (today, rec['amount'], rec['category'], rec['name'], f"Recurring payment: {rec['name']}", rec['account_id'])
        )
        
        next_due = advance_date(rec['next_due_date'], rec['interval'])
        cursor.execute(
            "UPDATE recurring_transactions SET next_due_date = ? WHERE id = ?",
            (next_due, recurring_id)
        )
        conn.commit()
        return {"status": "success", "next_due_date": next_due}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/recurring/{recurring_id}")
def delete_recurring(recurring_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM recurring_transactions WHERE id = ?", (recurring_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- FITNESS ---
@app.get("/api/fitness")
def get_fitness():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM fitness_logs ORDER BY date DESC")
        logs = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute(
            "SELECT activity_type, COUNT(*) as count, SUM(duration_minutes) as total_duration FROM fitness_logs GROUP BY activity_type"
        )
        stats = [dict(row) for row in cursor.fetchall()]
        
        return {"logs": logs, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/fitness")
def add_fitness(log: FitnessLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO fitness_logs (date, activity_type, duration_minutes, distance_km, calories_burned, intensity, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (log.date, log.activity_type, log.duration_minutes, log.distance_km, log.calories_burned, log.intensity, log.notes)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- HEALTH ---
def calculate_wellbeing_score(log_row, conn=None, cursor=None, has_workout=None, has_mindfulness=None):
    # sleep_hours (ideal: 7-9 hours)
    sleep = log_row.get("sleep_hours")
    if sleep is None:
        sleep_score = 12
    else:
        if 7.0 <= sleep <= 9.0:
            sleep_score = 20
        else:
            diff = min(abs(sleep - 8.0), 4) # cap diff at 4 hours
            sleep_score = max(0, int(20 - diff * 3))

    # mood (ideal: 10)
    mood_str = log_row.get("mood")
    mood_score = 12
    if mood_str:
        try:
            mood_val = float(re.findall(r"\d+\.?\d*", mood_str)[0])
            mood_score = min(20, int(mood_val * 2))
        except (ValueError, IndexError):
            pass

    # water_ml (ideal: 2000ml)
    water = log_row.get("water_ml") or 0
    water_score = min(20, int((water / 2000.0) * 20))

    # energy_level (ideal: 10)
    energy = log_row.get("energy_level")
    energy_score = 12 if energy is None else min(20, int(energy * 2))

    # stress_level (ideal: 1)
    stress = log_row.get("stress_level")
    stress_score = 12 if stress is None else min(20, int((11 - stress) * 2))

    # activity bonuses
    date = log_row.get("date")
    
    if has_workout is None:
        if cursor is not None:
            cursor.execute("SELECT COUNT(*) FROM fitness_logs WHERE date = ?", (date,))
            has_workout = cursor.fetchone()[0] > 0
        else:
            has_workout = False
            
    if has_mindfulness is None:
        if cursor is not None:
            cursor.execute("SELECT COUNT(*) FROM mindfulness_logs WHERE date = ?", (date,))
            has_mindfulness = cursor.fetchone()[0] > 0
        else:
            has_mindfulness = False

    workout_bonus = 5 if has_workout else 0
    mindfulness_bonus = 5 if has_mindfulness else 0

    total_score = sleep_score + mood_score + water_score + energy_score + stress_score + workout_bonus + mindfulness_bonus
    return min(100, total_score)

@app.get("/api/health")
def get_health():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM health_logs ORDER BY date DESC LIMIT 30")
        rows = cursor.fetchall()
        
        dates = [row['date'] for row in rows]
        fitness_dates = set()
        mindfulness_dates = set()
        
        if dates:
            placeholder = ",".join(["?"] * len(dates))
            cursor.execute(f"SELECT date FROM fitness_logs WHERE date IN ({placeholder}) GROUP BY date HAVING COUNT(*) > 0", dates)
            fitness_dates = {r['date'] for r in cursor.fetchall()}
            
            cursor.execute(f"SELECT date FROM mindfulness_logs WHERE date IN ({placeholder}) GROUP BY date HAVING COUNT(*) > 0", dates)
            mindfulness_dates = {r['date'] for r in cursor.fetchall()}
            
        logs = []
        for row in rows:
            d = dict(row)
            d["wellbeing_score"] = calculate_wellbeing_score(
                d, 
                has_workout=(d["date"] in fitness_dates), 
                has_mindfulness=(d["date"] in mindfulness_dates)
            )
            logs.append(d)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/health")
def add_health(log: HealthLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT OR REPLACE INTO health_logs 
               (date, weight_lbs, sleep_hours, mood, systolic, diastolic, notes, water_ml, energy_level, stress_level) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (log.date, log.weight_lbs, log.sleep_hours, log.mood, log.systolic, log.diastolic, log.notes, log.water_ml, log.energy_level, log.stress_level)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- MEALS ---
@app.get("/api/meals")
def get_meals(date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if date:
            cursor.execute("SELECT * FROM meal_logs WHERE date = ? ORDER BY id ASC", (date,))
        else:
            cursor.execute("SELECT * FROM meal_logs ORDER BY date DESC, id ASC")
        return {"meals": [dict(row) for row in cursor.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/meals")
def add_meal(meal: MealLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO meal_logs 
               (date, meal_type, description, calories, protein_g, carbs_g, fat_g) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (meal.date, meal.meal_type, meal.description, meal.calories, meal.protein_g, meal.carbs_g, meal.fat_g)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/meals/{meal_id}")
def delete_meal(meal_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM meal_logs WHERE id = ?", (meal_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- MINDFULNESS ---
@app.get("/api/mindfulness")
def get_mindfulness(date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if date:
            cursor.execute("SELECT * FROM mindfulness_logs WHERE date = ? ORDER BY id ASC", (date,))
        else:
            cursor.execute("SELECT * FROM mindfulness_logs ORDER BY date DESC, id ASC")
        return {"mindfulness": [dict(row) for row in cursor.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/mindfulness")
def add_mindfulness(session: MindfulnessLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO mindfulness_logs 
               (date, activity_type, duration_minutes, notes) 
               VALUES (?, ?, ?, ?)""",
            (session.date, session.activity_type, session.duration_minutes, session.notes)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/mindfulness/{mindfulness_id}")
def delete_mindfulness(mindfulness_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM mindfulness_logs WHERE id = ?", (mindfulness_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- LEARNING ---
@app.get("/api/learning")
def get_learning():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM learning_progress ORDER BY date DESC")
        logs = [dict(row) for row in cursor.fetchall()]
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/learning")
def add_learning(log: LearningProgressCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO learning_progress (date, topic, category, hours_spent, notes, source_link, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (log.date, log.topic, log.category, log.hours_spent, log.notes, log.source_link, log.status)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- CAREER ---
@app.get("/api/career")
def get_career():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM job_applications ORDER BY date_applied DESC")
        apps = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM job_leads WHERE status = 'lead' ORDER BY match_score DESC, tier ASC, date_found DESC")
        leads = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM career_search_profiles")
        profiles = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM job_leads WHERE is_remote = 1")
        tier1_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM job_leads WHERE tier = 2")
        tier2_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM job_applications WHERE outreach_status = 'pending'")
        pending_outreach = cursor.fetchone()[0] or 0
        
        return {
            "applications": apps, 
            "leads": leads, 
            "profiles": profiles,
            "stats": {
                "total_leads": len(leads),
                "total_applications": len(apps),
                "tier1_count": tier1_count,
                "tier2_count": tier2_count,
                "pending_outreach": pending_outreach
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/career")
def add_career(app_data: JobApplicationCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO job_applications (date_applied, company, role, salary_range, status, job_description_url, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (app_data.date_applied, app_data.company, app_data.role, app_data.salary_range, app_data.status, app_data.job_description_url, app_data.notes)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/career/profiles")
def add_career_profile(prof: CareerProfileCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO career_search_profiles (name, resume_path, keywords, locations, active) VALUES (?, ?, ?, ?, ?)",
            (prof.name, prof.resume_path, prof.keywords, prof.locations, prof.active)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/career/profiles/{profile_id}")
def delete_career_profile(profile_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM career_search_profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/career/leads/url")
def add_lead_by_url(data: JobLeadUrlIngest):
    from playwright.sync_api import sync_playwright
    
    url = data.url
    profile_id = data.profile_id
    
    # Store path relative to parent dir
    base_dir = os.path.dirname(os.path.abspath(__file__))
    CONTEXT_DIR = os.path.join(os.path.dirname(base_dir), "storage", "playwright_context")
    os.makedirs(os.path.dirname(CONTEXT_DIR), exist_ok=True)
    
    with sync_playwright() as p:
        try:
            if os.path.exists(CONTEXT_DIR):
                context = p.chromium.launch_persistent_context(
                    user_data_dir=CONTEXT_DIR,
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
            else:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                context = browser.new_context()
                
            page = context.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(2000)
            
            title = page.title() or "Unknown Role"
            company = "Unknown Company"
            description = page.locator("body").inner_text()[:2000]
            location = "Unknown Location"
            source = "manual"
            
            # Simple domain extraction
            parsed_domain = urlparse(url).netloc
            if "linkedin.com" in parsed_domain:
                source = "linkedin"
                comp_elem = page.query_selector("span.topcard__flavor a, a.topcard__org-name-link, .job-details-company-name, .job-details-company-name a")
                if comp_elem:
                    company = comp_elem.inner_text().strip()
                title_elem = page.query_selector("h1.top-card-layout__title, h1.job-details-title, h1.text-display-5")
                if title_elem:
                    title = title_elem.inner_text().strip()
                desc_elem = page.query_selector("article.jobs-description__content, .jobs-box__html-content, #job-details")
                if desc_elem:
                    description = desc_elem.inner_text().strip()
                loc_elem = page.query_selector(".topcard__flavor--bullet, .job-details-location")
                if loc_elem:
                    location = loc_elem.inner_text().strip()
            elif "indeed.com" in parsed_domain:
                source = "indeed"
                comp_elem = page.query_selector("[data-testid='company-name']")
                if comp_elem:
                    company = comp_elem.inner_text().strip()
                title_elem = page.query_selector("h1.jobsearch-JobInfoHeader-title")
                if title_elem:
                    title = title_elem.inner_text().strip()
                desc_elem = page.query_selector("#jobDescriptionText")
                if desc_elem:
                    description = desc_elem.inner_text().strip()
            elif "joinhandshake.com" in parsed_domain:
                source = "handshake"
                comp_elem = page.query_selector(".style__employer-name___3c_qY, .employer-name")
                if comp_elem:
                    company = comp_elem.inner_text().strip()
                title_elem = page.query_selector("h1")
                if title_elem:
                    title = title_elem.inner_text().strip()
                desc_elem = page.query_selector("[data-hook='job-description']")
                if desc_elem:
                    description = desc_elem.inner_text().strip()
            
            if "?" in url:
                url = url.split("?")[0]
                
            conn = get_db_connection()
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO job_leads (date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
                VALUES (?, ?, ?, ?, '', ?, ?, ?, 'lead', ?)
            """, (today, company, title, location, description, url, source, profile_id))
            conn.commit()
            lead_id = cursor.lastrowid
            conn.close()
            return {"status": "success", "lead_id": lead_id, "title": title, "company": company}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {str(e)}")
        finally:
            try:
                context.close()
            except Exception:
                pass

@app.post("/api/career/leads/{lead_id}/ignore")
def ignore_lead(lead_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE job_leads SET status = 'ignored' WHERE id = ?", (lead_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/career/leads/{lead_id}/process")
@app.post("/api/career/leads/{lead_id}/approve")
def process_lead(lead_id: int):
    try:
        app_id = job_tailor_engine.tailor_job_lead(lead_id)
        return {"status": "success", "application_id": app_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/career/applications/{app_id}")
def update_job_application(app_id: int, app_data: JobApplicationUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM job_applications WHERE id = ?", (app_id,))
        app = cursor.fetchone()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        update_fields = []
        params = []
        
        if app_data.recruiter_name is not None:
            update_fields.append("recruiter_name = ?")
            params.append(app_data.recruiter_name)
        if app_data.recruiter_email is not None:
            update_fields.append("recruiter_email = ?")
            params.append(app_data.recruiter_email)
        if app_data.cold_email_draft is not None:
            update_fields.append("cold_email_draft = ?")
            params.append(app_data.cold_email_draft)
        if app_data.tailored_bullets is not None:
            update_fields.append("tailored_bullets = ?")
            params.append(app_data.tailored_bullets)
        if app_data.cover_letter is not None:
            update_fields.append("cover_letter = ?")
            params.append(app_data.cover_letter)
        if app_data.status is not None:
            update_fields.append("status = ?")
            params.append(app_data.status)
            
        if not update_fields:
            return {"status": "no_change", "id": app_id}
            
        params.append(app_id)
        query = f"UPDATE job_applications SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        return {"status": "success", "id": app_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/career/applications/{app_id}/send-email")
def send_outreach_email(app_id: int):
    smtp_server = os.getenv("OUTREACH_SMTP_SERVER", "")
    smtp_port = os.getenv("OUTREACH_SMTP_PORT", "")
    sender_email = os.getenv("OUTREACH_EMAIL", "")
    sender_password = os.getenv("OUTREACH_PASSWORD", "")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM job_applications WHERE id = ?", (app_id,))
        app = cursor.fetchone()
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
            
        if not app['recruiter_email'] or not app['cold_email_draft']:
            raise HTTPException(status_code=400, detail="Missing recruiter email or cold email draft details.")
            
        if not smtp_server or not sender_email or not sender_password:
            # If SMTP is not fully configured, log the email in outreach_logs and update status to 'sent'
            cursor.execute("""
                INSERT INTO outreach_logs (application_id, recipient_email, subject, body, status)
                VALUES (?, ?, ?, ?, 'staged')
            """, (
                app_id, app['recruiter_email'],
                f"Inquiry regarding {app['role']} role at {app['company']} - Colby Gross",
                app['cold_email_draft']
            ))
            cursor.execute("UPDATE job_applications SET outreach_status = 'sent' WHERE id = ?", (app_id,))
            conn.commit()
            return {"status": "success", "message": "Email draft logged and staged! (Configure SMTP in .env for direct transmission)"}
            
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Construct Email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = app['recruiter_email']
        msg['Subject'] = f"Inquiry regarding {app['role']} role at {app['company']} - Colby Gross"
        
        msg.attach(MIMEText(app['cold_email_draft'], 'plain'))
        
        # Connect to SMTP
        port = int(smtp_port) if smtp_port else 587
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, app['recruiter_email'], msg.as_string())
        server.quit()
        
        # Update status in DB
        cursor.execute("UPDATE job_applications SET outreach_status = 'sent' WHERE id = ?", (app_id,))
        cursor.execute("""
            INSERT INTO outreach_logs (application_id, recipient_email, subject, body, status)
            VALUES (?, ?, ?, ?, 'sent')
        """, (
            app_id, app['recruiter_email'],
            f"Inquiry regarding {app['role']} role at {app['company']} - Colby Gross",
            app['cold_email_draft']
        ))
        conn.commit()
        return {"status": "success", "message": "Email sent successfully!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    finally:
        conn.close()

def run_scraper_in_background():
    try:
        print("Starting background job discovery & tailoring engine...")
        added = job_discovery_engine.run_discovery_pipeline()
        print(f"Job discovery added {added} new leads. Starting batch tailoring...")
        tailored = job_tailor_engine.batch_tailor_top_leads(5)
        print(f"Batch tailoring completed. Created {len(tailored)} tailored packets.")
    except Exception as e:
        print(f"Background discovery error: {e}")

@app.post("/api/career/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper_in_background)
    return {"status": "started", "message": "Job discovery engine started in background."}


# --- HABITS ---
@app.get("/api/habits")
def get_habits():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get habits from the last 14 days
        two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT * FROM habit_logs WHERE date >= ? ORDER BY date DESC, habit_name ASC",
            (two_weeks_ago,)
        )
        logs = [dict(row) for row in cursor.fetchall()]
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/habits")
def add_habit_log(log: HabitLogCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO habit_logs (date, habit_name, completed, notes) VALUES (?, ?, ?, ?)",
            (log.date, log.habit_name, log.completed, log.notes)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- TASKS ---
class TaskCreate(BaseModel):
    title: str
    category: str = "general"
    due_date: Optional[str] = None
    priority: str = "medium"
    importance: str = "minor"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    importance: Optional[str] = None

@app.get("/api/tasks")
def get_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks ORDER BY status DESC, due_date ASC, created_at DESC")
        tasks = [dict(row) for row in cursor.fetchall()]
        return {"tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/tasks")
def add_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tasks (title, category, status, due_date, source_file, priority, importance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task.title, task.category, "pending", task.due_date, "tasks.md", task.priority, task.importance)
        )
        conn.commit()
        task_id = cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    try:
        agent.sync_db_to_tasks_md_helper()
    except Exception as e:
        print(f"Error updating tasks.md: {e}")
        
    return {"status": "success", "id": task_id}

@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, task_data: TaskUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        update_fields = []
        params = []
        
        if task_data.title is not None:
            update_fields.append("title = ?")
            params.append(task_data.title)
        if task_data.category is not None:
            update_fields.append("category = ?")
            params.append(task_data.category)
        if task_data.status is not None:
            update_fields.append("status = ?")
            params.append(task_data.status)
            if task_data.status == "completed":
                update_fields.append("completed_at = ?")
                params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                update_fields.append("completed_at = ?")
                params.append(None)
        if task_data.due_date is not None:
            due_val = task_data.due_date if task_data.due_date.strip() != "" else None
            update_fields.append("due_date = ?")
            params.append(due_val)
        if task_data.priority is not None:
            update_fields.append("priority = ?")
            params.append(task_data.priority)
        if task_data.importance is not None:
            update_fields.append("importance = ?")
            params.append(task_data.importance)
            
        if not update_fields:
            return {"status": "no_change", "id": task_id}
            
        params.append(task_id)
        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    source_file = task['source_file']
    
    if task_data.status is not None and task_data.status != task['status'] and source_file and source_file != "tasks.md":
        try:
            agent.toggle_task_in_file(agent.VAULT_DIR, source_file, task['title'], task_data.status == "completed")
        except Exception as e:
            print(f"Error toggling task in source file {source_file}: {e}")
            
    try:
        agent.sync_db_to_tasks_md_helper()
    except Exception as e:
        print(f"Error updating tasks.md: {e}")
        
    return {"status": "success", "id": task_id}

@app.put("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        new_status = "completed" if task['status'] == 'pending' else "pending"
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "completed" else None
        
        cursor.execute(
            "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
            (new_status, completed_at, task_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    # Write back to file system
    source_file = task['source_file']
    title = task['title']
    
    if source_file and source_file != "tasks.md":
        try:
            agent.toggle_task_in_file(agent.VAULT_DIR, source_file, title, new_status == "completed")
        except Exception as e:
            print(f"Error toggling task in source file {source_file}: {e}")
            
    try:
        agent.sync_db_to_tasks_md_helper()
    except Exception as e:
        print(f"Error updating tasks.md: {e}")
        
    return {"status": "success", "task_id": task_id, "new_status": new_status}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    try:
        agent.sync_db_to_tasks_md_helper()
    except Exception as e:
        print(f"Error updating tasks.md: {e}")
        
    return {"status": "success"}

# --- CALENDAR ---
class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: str
    end_time: str

@app.get("/api/calendar")
def get_calendar():
    try:
        agent.sync_local_ics_to_db()
    except Exception as e:
        print(f"Error syncing local ICS on GET calendar: {e}")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM calendar_events ORDER BY start_time ASC")
        events = [dict(row) for row in cursor.fetchall()]
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/calendar")
def add_calendar_event(event: CalendarEventCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    event_uid = f"{uuid.uuid4()}@local"
    try:
        cursor.execute(
            """INSERT INTO calendar_events 
               (title, description, start_time, end_time, source, event_uid) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event.title, event.description, event.start_time, event.end_time, "local_ics", event_uid)
        )
        conn.commit()
        event_id = cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    try:
        agent.serialize_local_events_to_ics_helper()
    except Exception as e:
        print(f"Error serializing local events: {e}")
        
    return {"status": "success", "id": event_id, "event_uid": event_uid}

@app.delete("/api/calendar/{event_id}")
def delete_calendar_event(event_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
            
        if event['source'] != 'local_ics':
            raise HTTPException(status_code=400, detail="Cannot delete Google Calendar events")
            
        cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    try:
        agent.serialize_local_events_to_ics_helper()
    except Exception as e:
        print(f"Error serializing local calendar: {e}")
        
    return {"status": "success"}

# --- AGENT CONTROLLER ---
def run_agent_in_background():
    global agent_running
    with agent_lock:
        if agent_running:
            return
        agent_running = True
        
    try:
        print("Starting background Athena agent synchronization run...")
        agent.run_agent_sync()
        print("Background Athena agent synchronization completed successfully.")
    except Exception as e:
        print(f"Background agent execution error: {e}")
    finally:
        with agent_lock:
            agent_running = False

@app.post("/api/agent/run")
def trigger_agent(background_tasks: BackgroundTasks):
    global agent_running
    with agent_lock:
        if agent_running:
            return {"status": "already_running", "message": "Agent is currently processing."}
            
    background_tasks.add_task(run_agent_in_background)
    return {"status": "started", "message": "Athena synchronization agent started in the background."}

@app.get("/api/agent/status")
def get_agent_status():
    global agent_running
    
    inbox_files = []
    if os.path.exists(agent.INBOX_DIR):
        inbox_files = [f for f in os.listdir(agent.INBOX_DIR) if os.path.isfile(os.path.join(agent.INBOX_DIR, f))]
        
    return {
        "status": "running" if agent_running else "idle",
        "inbox_count": len(inbox_files),
        "inbox_files": inbox_files
    }

# --- DAILY BRIEFS ---
@app.get("/api/daily-briefs")
def get_daily_briefs():
    briefs_dir = os.path.join(agent.VAULT_DIR, "Daily_Briefs")
    if not os.path.exists(briefs_dir):
        return {"briefs": []}
    
    briefs = []
    pattern = re.compile(r"^Daily_Brief_(\d{4}-\d{2}-\d{2})\.md$")
    for f in os.listdir(briefs_dir):
        m = pattern.match(f)
        if m:
            date_str = m.group(1)
            briefs.append({
                "date": date_str,
                "filename": f
            })
    
    briefs.sort(key=lambda x: x["date"], reverse=True)
    return {"briefs": briefs}

@app.get("/api/daily-briefs/{date}")
def get_daily_brief(date: str):
    briefs_dir = os.path.join(agent.VAULT_DIR, "Daily_Briefs")
    filename = f"Daily_Brief_{date}.md"
    file_path = os.path.join(briefs_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Daily Brief for {date} not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"date": date, "filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/daily-briefs/generate")
def generate_new_brief():
    try:
        agent.generate_daily_brief()
        today = datetime.now().strftime("%Y-%m-%d")
        briefs_dir = os.path.join(agent.VAULT_DIR, "Daily_Briefs")
        file_path = os.path.join(briefs_dir, f"Daily_Brief_{today}.md")
        content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        return {"status": "success", "date": today, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- PROJECTS WORKSPACE ---
class ProjectUpdate(BaseModel):
    content: str

@app.get("/api/projects")
def get_projects():
    projects_dir = os.path.join(agent.VAULT_DIR, "01_Projects")
    if not os.path.exists(projects_dir):
        return {"projects": []}
    
    projects = []
    for file in os.listdir(projects_dir):
        if file.endswith(".md"):
            title = os.path.splitext(file)[0].replace("_", " ")
            projects.append({
                "filename": file,
                "title": title
            })
    return {"projects": sorted(projects, key=lambda x: x["title"])}

@app.get("/api/projects/{filename}")
def get_project_content(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    projects_dir = os.path.join(agent.VAULT_DIR, "01_Projects")
    file_path = os.path.join(projects_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{filename}")
def update_project(filename: str, project: ProjectUpdate, background_tasks: BackgroundTasks):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    projects_dir = os.path.join(agent.VAULT_DIR, "01_Projects")
    file_path = os.path.join(projects_dir, filename)
    
    try:
        os.makedirs(projects_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(project.content)
        
        background_tasks.add_task(run_agent_in_background)
        return {"status": "success", "message": "Project updated and sync triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- RESOURCES WORKSPACE ---
class ResourceUpdate(BaseModel):
    content: str

@app.get("/api/resources")
def get_resources():
    resources_dir = os.path.join(agent.VAULT_DIR, "03_Resources")
    if not os.path.exists(resources_dir):
        return {"resources": []}
    
    resources = []
    for file in os.listdir(resources_dir):
        if file.endswith(".md"):
            title = os.path.splitext(file)[0].replace("_", " ")
            resources.append({
                "filename": file,
                "title": title
            })
    return {"resources": sorted(resources, key=lambda x: x["title"])}

@app.get("/api/resources/{filename}")
def get_resource_content(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    resources_dir = os.path.join(agent.VAULT_DIR, "03_Resources")
    file_path = os.path.join(resources_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resource not found")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/resources/{filename}")
def update_resource(filename: str, resource: ResourceUpdate, background_tasks: BackgroundTasks):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    resources_dir = os.path.join(agent.VAULT_DIR, "03_Resources")
    file_path = os.path.join(resources_dir, filename)
    
    try:
        os.makedirs(resources_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(resource.content)
        
        background_tasks.add_task(run_agent_in_background)
        return {"status": "success", "message": "Resource updated and sync triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- AREAS WORKSPACE ---
class AreaUpdate(BaseModel):
    content: str

@app.get("/api/areas")
def get_areas():
    areas_dir = os.path.join(agent.VAULT_DIR, "02_Areas")
    if not os.path.exists(areas_dir):
        return {"areas": []}
    
    areas = []
    # Walk the areas directory to find all markdown files
    for root, dirs, files in os.walk(areas_dir):
        for file in files:
            if file.endswith(".md"):
                rel_path = os.path.relpath(root, areas_dir)
                category = rel_path
                title = os.path.splitext(file)[0].replace("_", " ")
                areas.append({
                    "category": category,
                    "filename": file,
                    "title": title
                })
    return {"areas": sorted(areas, key=lambda x: (x["category"], x["title"]))}

@app.get("/api/areas/{category}/{filename}")
def get_area_content(category: str, filename: str):
    if ".." in category or "/" in category or "\\" in category:
        raise HTTPException(status_code=400, detail="Invalid category")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    areas_dir = os.path.join(agent.VAULT_DIR, "02_Areas")
    file_path = os.path.join(areas_dir, category, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Area note not found")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"category": category, "filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/areas/{category}/{filename}")
def update_area(category: str, filename: str, area: AreaUpdate, background_tasks: BackgroundTasks):
    if ".." in category or "/" in category or "\\" in category:
        raise HTTPException(status_code=400, detail="Invalid category")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    areas_dir = os.path.join(agent.VAULT_DIR, "02_Areas")
    file_path = os.path.join(areas_dir, category, filename)
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(area.content)
        
        background_tasks.add_task(run_agent_in_background)
        return {"status": "success", "message": "Area note updated and sync triggered."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve static files for frontend dashboard on root path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
    
    @app.get("/")
    async def serve_index():
        # Never cache index.html: hashed asset names change on each build, so a
        # cached index would keep loading a stale bundle (breaks remote access).
        return FileResponse(os.path.join(dist_path, "index.html"), headers={"Cache-Control": "no-cache"})
        
    @app.get("/{file_name}")
    async def serve_root_files(file_name: str):
        file_path = os.path.join(dist_path, file_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
