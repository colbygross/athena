"""
Athena MCP server: lets external agents (Claude Code, cloud routines, ...) read Athena's
data and record job-hunt activity.

Mounted inside the FastAPI app at /mcp (Streamable HTTP, stateless, JSON responses).
Every request needs `Authorization: Bearer <token>`: either an OAuth access token issued by
oauth.py (how claude.ai connectors and other MCP clients sign in) or a static per-agent token
managed with backend/mcp_tokens.py. Both carry scopes and are stored as SHA-256 hashes.

Scopes: one read scope per domain (DOMAINS) plus `career:write`. Everything except career
is read-only. Each token is rate limited and every tool call is logged in mcp_call_log.
"""
import contextvars
import functools
import hashlib
import json
import os
import secrets
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

import agent
import career
import finance
from database import create_new_connection

DOMAINS = ("career", "calendar", "tasks", "finances", "health", "learning", "habits", "notes")
WRITE_SCOPES = ("career:write",)
ALL_SCOPES = DOMAINS + WRITE_SCOPES
SCOPE_PRESETS = {
    "job-agent": ["career", "calendar", "tasks", "career:write"],
    "full-read": list(DOMAINS),
}

RATE_LIMIT_PER_MINUTE = int(os.getenv("MCP_RATE_LIMIT_PER_MINUTE", "60"))
MAX_ROWS = 500

# Vault folders agents may read with list_notes / read_note (Inbox holds unprocessed uploads).
NOTE_FOLDERS = ("Daily_Briefs", "Summaries", "01_Projects", "02_Areas", "03_Resources", "04_Archives")
MAX_NOTE_CHARS = 200_000

# The authenticated agent for the current request: {"name": str, "scopes": set[str]}.
current_agent = contextvars.ContextVar("athena_mcp_agent", default=None)


# --- Tokens -------------------------------------------------------------------

def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(name, scopes):
    """Create a token for an agent and return the plaintext (shown once, never stored)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Token name is required")
    unknown = set(scopes) - set(ALL_SCOPES)
    if unknown:
        raise ValueError(f"Unknown scopes: {', '.join(sorted(unknown))}. Valid: {', '.join(ALL_SCOPES)}")
    if not scopes:
        raise ValueError("At least one scope is required")
    token = "ath_" + secrets.token_urlsafe(32)
    conn = create_new_connection()
    try:
        conn.execute(
            "INSERT INTO mcp_tokens (name, token_hash, scopes) VALUES (?, ?, ?)",
            (name, hash_token(token), json.dumps(sorted(set(scopes))))
        )
        conn.commit()
    finally:
        conn.close()
    return token


def revoke_token(name):
    """Revoke an agent's token. Returns False if no active token has that name."""
    conn = create_new_connection()
    try:
        cur = conn.execute(
            "UPDATE mcp_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE name = ? AND revoked_at IS NULL", (name,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_tokens():
    conn = create_new_connection()
    try:
        rows = conn.execute(
            "SELECT name, scopes, created_at, last_used_at, revoked_at FROM mcp_tokens ORDER BY created_at"
        ).fetchall()
        return [{**dict(r), "scopes": json.loads(r["scopes"])} for r in rows]
    finally:
        conn.close()


def authenticate(token):
    """Return {"name", "scopes"} for an active token, or None."""
    if not token:
        return None
    conn = create_new_connection()
    try:
        row = conn.execute(
            "SELECT id, name, scopes FROM mcp_tokens WHERE token_hash = ? AND revoked_at IS NULL",
            (hash_token(token),)
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE mcp_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        conn.commit()
        return {"name": row["name"], "scopes": set(json.loads(row["scopes"]))}
    finally:
        conn.close()


class RateLimiter:
    """Sliding one-minute window per token name."""

    def __init__(self, per_minute):
        self.per_minute = per_minute
        self._calls = {}
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            calls = self._calls.setdefault(key, deque())
            while calls and now - calls[0] >= 60:
                calls.popleft()
            if len(calls) >= self.per_minute:
                return False
            calls.append(now)
            return True


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


# --- HTTP endpoint ------------------------------------------------------------

_session_manager = None


@asynccontextmanager
async def lifespan():
    """Run the MCP session manager for the life of the web app (a new one per startup)."""
    global _session_manager
    manager = StreamableHTTPSessionManager(app=mcp._mcp_server, json_response=True, stateless=True)
    async with manager.run():
        _session_manager = manager
        try:
            yield
        finally:
            _session_manager = None


async def _send_json(send, status, body, headers=()):
    payload = json.dumps(body).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode()), *headers],
    })
    await send({"type": "http.response.body", "body": payload})


class MCPEndpoint:
    """ASGI app for /mcp: bearer auth and rate limiting in front of the MCP session manager."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        import oauth  # imported here: oauth imports this module
        agent_info = authenticate(token) or oauth.verify_access_token(token)
        if agent_info is None:
            # RFC 9728: point OAuth clients at the protected resource metadata so they can sign in.
            challenge = f'Bearer error="invalid_token", resource_metadata="{oauth.PROTECTED_RESOURCE_METADATA_URL}"'
            await _send_json(send, 401, {"error": "invalid_token", "detail": "Missing or invalid bearer token"},
                             [(b"www-authenticate", challenge.encode())])
            return
        if not rate_limiter.allow(agent_info["name"]):
            await _send_json(send, 429, {"error": "rate_limited",
                                         "detail": f"More than {RATE_LIMIT_PER_MINUTE} requests per minute"},
                             [(b"retry-after", b"60")])
            return
        if _session_manager is None:
            await _send_json(send, 503, {"error": "unavailable", "detail": "MCP server is not running"})
            return
        reset = current_agent.set(agent_info)
        try:
            await _session_manager.handle_request(scope, receive, send)
        finally:
            current_agent.reset(reset)


endpoint = MCPEndpoint()


# --- Tool plumbing ------------------------------------------------------------

mcp = FastMCP(
    "athena",
    instructions=(
        "Athena is the user's personal life dashboard. Read their calendar, tasks, finances, health, "
        "learning, habits and Obsidian notes; record their job hunt (applications, timeline events, leads). "
        "Dates are YYYY-MM-DD and times are the user's local time ('YYYY-MM-DD HH:MM:SS'). "
        "Only career data can be changed. log_application and add_lead are safe to repeat: duplicates are updated."
    ),
)


def _log_call(agent_name, tool, ok, error=None):
    try:
        conn = create_new_connection()
        try:
            conn.execute(
                "INSERT INTO mcp_call_log (token_name, tool, ok, error) VALUES (?, ?, ?, ?)",
                (agent_name, tool, int(ok), error)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"Could not write MCP call log: {e}")


def athena_tool(scope):
    """Register an MCP tool that needs `scope`. The function gets an open connection as `conn`."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            agent_info = current_agent.get()
            name = agent_info["name"] if agent_info else "unknown"
            if not agent_info or scope not in agent_info["scopes"]:
                _log_call(name, fn.__name__, False, f"missing scope {scope}")
                raise ToolError(f"This token does not have the '{scope}' scope.")
            conn = create_new_connection()
            try:
                result = fn(conn, *args, **kwargs)
                conn.commit()
            except career.CareerError as e:
                conn.rollback()
                _log_call(name, fn.__name__, False, str(e))
                raise ToolError(str(e))
            except Exception as e:
                conn.rollback()
                _log_call(name, fn.__name__, False, repr(e))
                raise
            finally:
                conn.close()
            _log_call(name, fn.__name__, True)
            # Return one JSON object: FastMCP would otherwise split a list into one content block per row
            # (and send nothing at all for an empty list).
            if isinstance(result, list):
                return {"count": len(result), "items": result}
            return result

        # FastMCP builds the tool schema from the signature: hide the injected `conn`.
        import inspect
        sig = inspect.signature(fn)
        wrapper.__signature__ = sig.replace(parameters=[p for n, p in sig.parameters.items() if n != "conn"])
        del wrapper.__wrapped__
        mcp.tool()(wrapper)
        return fn
    return decorator


def _agent_name():
    agent_info = current_agent.get()
    return agent_info["name"] if agent_info else None


def _limit(limit):
    return max(1, min(int(limit), MAX_ROWS))


def _date(value, field):
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        raise ToolError(f"{field} must be a date like YYYY-MM-DD")


def _rows(cursor, sql, params=()):
    cursor.execute(sql, params)
    return [dict(r) for r in cursor.fetchall()]


def _where(clauses, params, column, op, value):
    if value is not None:
        clauses.append(f"{column} {op} ?")
        params.append(value)


# --- Read tools ---------------------------------------------------------------

@mcp.tool()
def get_overview() -> dict:
    """Snapshot of today across every domain this token can read (sections without scope are omitted)."""
    agent_info = current_agent.get()
    if not agent_info:
        raise ToolError("Not authenticated.")
    scopes = agent_info["scopes"]
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    out = {"date": today}
    conn = create_new_connection()
    try:
        cur = conn.cursor()
        if "calendar" in scopes:
            out["events_today"] = _rows(cur, """SELECT id, title, start_time, end_time FROM calendar_events
                WHERE start_time <= ? AND end_time >= ? ORDER BY start_time""", (f"{today} 23:59:59", f"{today} 00:00:00"))
        if "tasks" in scopes:
            cur.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
            pending = cur.fetchone()[0]
            out["tasks"] = {
                "pending": pending,
                "overdue": _rows(cur, "SELECT id, title, due_date, priority FROM tasks WHERE status = 'pending' AND due_date < ? ORDER BY due_date", (today,)),
                "due_today": _rows(cur, "SELECT id, title, priority FROM tasks WHERE status = 'pending' AND due_date = ?", (today,)),
            }
        if "finances" in scopes:
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND date LIKE ?", (f"{today[:7]}%",))
            out["finances"] = {"spent_this_month": cur.fetchone()[0], "net_wealth": finance.net_wealth(finance.account_balances(cur))}
        if "health" in scopes:
            latest = _rows(cur, "SELECT * FROM health_logs ORDER BY date DESC LIMIT 1")
            cur.execute("SELECT COUNT(*) FROM fitness_logs WHERE date >= ?", (week_ago,))
            out["health"] = {"latest_vitals": latest[0] if latest else None, "workouts_last_7_days": cur.fetchone()[0]}
        if "habits" in scopes:
            out["habits_today"] = _rows(cur, "SELECT habit_name, completed FROM habit_logs WHERE date = ?", (today,))
        if "learning" in scopes:
            cur.execute("SELECT COALESCE(SUM(hours_spent), 0) FROM learning_progress WHERE date >= ?", (week_ago,))
            out["learning_hours_last_7_days"] = cur.fetchone()[0]
        if "career" in scopes:
            out["career"] = career.career_stats(conn)
    finally:
        conn.close()
    _log_call(agent_info["name"], "get_overview", True)
    return out


@athena_tool("calendar")
def list_events(conn, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 200) -> dict:
    """Calendar events overlapping [start_date, end_date] (default: today through the next 14 days)."""
    start = _date(start_date, "start_date") or datetime.now().strftime("%Y-%m-%d")
    end = _date(end_date, "end_date") or (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")
    events = _rows(conn.cursor(), """SELECT id, title, description, start_time, end_time, source, tags FROM calendar_events
        WHERE start_time <= ? AND end_time >= ? ORDER BY start_time LIMIT ?""",
                   (f"{end} 23:59:59", f"{start} 00:00:00", _limit(limit)))
    for ev in events:
        try:
            ev["tags"] = json.loads(ev["tags"]) if ev["tags"] else []
        except ValueError:
            ev["tags"] = []
    return events


@athena_tool("tasks")
def list_tasks(conn, status: Optional[str] = "pending", due_before: Optional[str] = None,
               category: Optional[str] = None, limit: int = 200) -> dict:
    """Tasks with their subtasks. status: 'pending', 'completed', or null for both. due_before: YYYY-MM-DD (inclusive)."""
    if status not in (None, "pending", "completed"):
        raise ToolError("status must be 'pending', 'completed' or null")
    clauses, params = [], []
    _where(clauses, params, "status", "=", status)
    _where(clauses, params, "due_date", "<=", _date(due_before, "due_before"))
    _where(clauses, params, "category", "=", category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cur = conn.cursor()
    tasks = _rows(cur, f"""SELECT id, title, category, status, due_date, priority, importance, estimated_minutes,
        recurrence, completed_at, source_file, event_id FROM tasks {where}
        ORDER BY due_date IS NULL, due_date, id LIMIT ?""", (*params, _limit(limit)))
    for t in tasks:
        t["subtasks"] = _rows(cur, "SELECT title, is_completed FROM task_subtasks WHERE task_id = ? ORDER BY position, id", (t["id"],))
    return tasks


@athena_tool("finances")
def list_transactions(conn, start_date: Optional[str] = None, end_date: Optional[str] = None,
                      account_id: Optional[int] = None, category: Optional[str] = None, limit: int = 200) -> dict:
    """Transactions, newest first, filtered by date range (YYYY-MM-DD, inclusive), account and category."""
    clauses, params = [], []
    _where(clauses, params, "t.date", ">=", _date(start_date, "start_date"))
    _where(clauses, params, "t.date", "<=", _date(end_date, "end_date"))
    _where(clauses, params, "t.account_id", "=", account_id)
    _where(clauses, params, "t.category", "=", category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.cursor(), f"""SELECT t.id, t.date, t.amount, t.type, t.category, t.merchant, t.description,
        t.account_id, a.name AS account_name, t.transfer_account_id FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id {where} ORDER BY t.date DESC, t.id DESC LIMIT ?""",
                 (*params, _limit(limit)))


@athena_tool("finances")
def get_finance_summary(conn) -> dict:
    """Account balances, net wealth, this month's spending by category vs. budgets, upcoming recurring payments, student loans."""
    cur = conn.cursor()
    accounts = finance.account_balances(cur)
    month = datetime.now().strftime("%Y-%m")
    return {
        "accounts": accounts,
        "net_wealth": finance.net_wealth(accounts),
        "month": month,
        "spending_by_category": _rows(cur, """SELECT category, SUM(amount) AS total FROM transactions
            WHERE type = 'expense' AND date LIKE ? GROUP BY category ORDER BY total DESC""", (f"{month}%",)),
        "budgets": finance.load_budgets(),
        "recurring": _rows(cur, """SELECT r.id, r.name, r.amount, r.interval, r.category, r.next_due_date, a.name AS account_name
            FROM recurring_transactions r LEFT JOIN accounts a ON r.account_id = a.id
            WHERE r.active = 1 ORDER BY r.next_due_date"""),
        "student_loans": _rows(cur, "SELECT * FROM student_loans ORDER BY name"),
    }


HEALTH_KINDS = {
    "vitals": "health_logs",
    "fitness": "fitness_logs",
    "meals": "meal_logs",
    "mindfulness": "mindfulness_logs",
}


@athena_tool("health")
def list_health_logs(conn, kind: str = "vitals", start_date: Optional[str] = None,
                     end_date: Optional[str] = None, limit: int = 60) -> dict:
    """Health records, newest first. kind: 'vitals' (weight, sleep, mood, BP, water, energy, stress), 'fitness', 'meals' or 'mindfulness'."""
    table = HEALTH_KINDS.get(kind)
    if not table:
        raise ToolError(f"kind must be one of {', '.join(HEALTH_KINDS)}")
    clauses, params = [], []
    _where(clauses, params, "date", ">=", _date(start_date, "start_date"))
    _where(clauses, params, "date", "<=", _date(end_date, "end_date"))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.cursor(), f"SELECT * FROM {table} {where} ORDER BY date DESC, id DESC LIMIT ?", (*params, _limit(limit)))


@athena_tool("learning")
def list_learning(conn, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> dict:
    """Learning log entries (topic, category, hours, notes), newest first."""
    clauses, params = [], []
    _where(clauses, params, "date", ">=", _date(start_date, "start_date"))
    _where(clauses, params, "date", "<=", _date(end_date, "end_date"))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.cursor(), f"SELECT * FROM learning_progress {where} ORDER BY date DESC, id DESC LIMIT ?", (*params, _limit(limit)))


@athena_tool("habits")
def list_habits(conn, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Habit check-ins (habit_name, completed 0/1) for a date range (default: the last 14 days)."""
    start = _date(start_date, "start_date") or (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    end = _date(end_date, "end_date") or datetime.now().strftime("%Y-%m-%d")
    return _rows(conn.cursor(), "SELECT date, habit_name, completed, notes FROM habit_logs WHERE date BETWEEN ? AND ? ORDER BY date DESC, habit_name",
                 (start, end))


@athena_tool("career")
def list_applications(conn, status: Optional[str] = None, limit: int = 100) -> dict:
    """Job applications, newest first. status: applied, interviewing, offered, rejected, withdrawn (or null for all)."""
    return career.list_applications(conn, status=status, limit=_limit(limit))


@athena_tool("career")
def get_application(conn, application_id: int) -> dict:
    """One job application with its full timeline of events."""
    return career.get_application(conn, application_id)


@athena_tool("career")
def list_leads(conn, status: Optional[str] = "lead", limit: int = 100) -> dict:
    """Job leads. status: 'lead' (open), 'ignored', 'applied', or null for all."""
    return career.list_leads(conn, status=status, limit=_limit(limit))


def _vault_path(relative_path):
    """Resolve a note path inside an allowed vault folder, or raise ToolError."""
    vault = os.path.realpath(agent.VAULT_DIR)
    full = os.path.realpath(os.path.join(vault, relative_path or ""))
    rel = os.path.relpath(full, vault)
    top = rel.split(os.sep, 1)[0]
    if rel.startswith("..") or top not in NOTE_FOLDERS:
        raise ToolError(f"Notes must be inside one of: {', '.join(NOTE_FOLDERS)}")
    return full, rel


@athena_tool("notes")
def list_notes(conn, folder: Optional[str] = None) -> dict:
    """Markdown notes in the Obsidian vault (daily briefs, summaries, projects, areas, resources, archives). folder: e.g. 'Daily_Briefs' or '02_Areas/Career'."""
    roots = [_vault_path(folder)[0]] if folder else [os.path.join(os.path.realpath(agent.VAULT_DIR), f) for f in NOTE_FOLDERS]
    vault = os.path.realpath(agent.VAULT_DIR)
    notes = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for f in filenames:
                if f.endswith(".md") and not f.startswith("."):
                    full = os.path.join(dirpath, f)
                    notes.append({
                        "path": os.path.relpath(full, vault).replace(os.sep, "/"),
                        "modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M:%S"),
                    })
    return sorted(notes, key=lambda n: n["path"])[:MAX_ROWS * 4]


@athena_tool("notes")
def read_note(conn, path: str) -> dict:
    """Read one markdown note by its vault path from list_notes (e.g. 'Daily_Briefs/Daily_Brief_2026-10-16.md')."""
    full, rel = _vault_path(path)
    if not full.endswith(".md") or not os.path.isfile(full):
        raise ToolError(f"No note at {path}")
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(MAX_NOTE_CHARS + 1)
    return {"path": rel.replace(os.sep, "/"), "content": content[:MAX_NOTE_CHARS], "truncated": len(content) > MAX_NOTE_CHARS}


# --- Career write tools -------------------------------------------------------

@athena_tool("career:write")
def log_application(conn, company: str, role: str, date_applied: Optional[str] = None, job_url: Optional[str] = None,
                    status: Optional[str] = None, salary_range: Optional[str] = None, notes: Optional[str] = None,
                    recruiter_name: Optional[str] = None, recruiter_email: Optional[str] = None) -> dict:
    """
    Record a job the user applied to. Safe to repeat: if an application with the same job URL,
    or the same company + role within 90 days, exists it is updated instead (blank fields are left alone).
    date_applied defaults to today; status defaults to 'applied' for new applications.
    Returns {"id", "result": "created" | "updated"}.
    """
    return career.log_application(conn, company, role, date_applied=date_applied, job_url=job_url, status=status,
                                  salary_range=salary_range, notes=notes, recruiter_name=recruiter_name,
                                  recruiter_email=recruiter_email, created_by=_agent_name())


@athena_tool("career:write")
def update_application_status(conn, application_id: int, status: str, note: Optional[str] = None,
                              event_date: Optional[str] = None) -> dict:
    """Move an application to applied, interviewing, offered, rejected or withdrawn; the change is added to its timeline."""
    changed = career.set_application_status(conn, application_id, status, note=note, event_date=event_date,
                                            created_by=_agent_name())
    return {"id": application_id, "status": status, "changed": changed}


@athena_tool("career:write")
def add_application_event(conn, application_id: int, kind: str, note: Optional[str] = None,
                          event_date: Optional[str] = None) -> dict:
    """
    Add a timeline entry to an application. kind: 'interview', 'recruiter_contact', 'offer', 'note'
    (use update_application_status for status changes). event_date (YYYY-MM-DD) defaults to today and may be in the future.
    """
    if kind == "status_change":
        raise ToolError("Use update_application_status to change status.")
    return {"id": career.add_application_event(conn, application_id, kind, note=note, event_date=event_date,
                                               created_by=_agent_name())}


@athena_tool("career:write")
def add_lead(conn, company: str, role: str, job_url: str, location: Optional[str] = None,
             salary_range: Optional[str] = None, description: Optional[str] = None, source: Optional[str] = None,
             is_remote: bool = False, match_score: Optional[int] = None) -> dict:
    """
    Suggest a job worth applying to. Safe to repeat: a lead with the same job URL is updated.
    match_score: optional 0-100 fit estimate. Returns {"id", "result": "created" | "updated"}.
    """
    return career.add_lead(conn, company, role, job_url, location=location, salary_range=salary_range,
                           description=description, source=source or _agent_name() or "agent", is_remote=is_remote,
                           match_score=match_score, created_by=_agent_name())


@athena_tool("career:write")
def dismiss_lead(conn, lead_id: int) -> dict:
    """Mark a lead as not interesting."""
    career.dismiss_lead(conn, lead_id)
    return {"id": lead_id, "status": "ignored"}


@athena_tool("career:write")
def promote_lead(conn, lead_id: int, date_applied: Optional[str] = None, notes: Optional[str] = None) -> dict:
    """The user applied to this lead: create (or update) the linked application and mark the lead applied."""
    return career.promote_lead(conn, lead_id, date_applied=date_applied, notes=notes, created_by=_agent_name())
