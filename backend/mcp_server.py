"""
Athena MCP server: lets external agents (Claude Code, cloud routines, ...) read Athena's
data and record job-hunt activity.

Mounted inside the FastAPI app at /mcp (Streamable HTTP, stateless, JSON responses).
Every request needs `Authorization: Bearer <token>`: either an OAuth access token issued by
oauth.py (how claude.ai connectors and other MCP clients sign in) or a static per-agent token
managed with backend/mcp_tokens.py. Both carry scopes and are stored as SHA-256 hashes.

Scopes: one read scope per domain (DOMAINS) and a matching `<domain>:write` scope. Private data
(privacy.py) is filtered out of every read and can't be changed. Each token is rate limited and
every tool call is logged in mcp_call_log.
"""
import contextvars
import sqlite3
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
import privacy
from database import create_new_connection

DOMAINS = ("career", "calendar", "tasks", "finances", "health", "learning", "habits", "notes")
WRITE_SCOPES = tuple(f"{d}:write" for d in DOMAINS)
ALL_SCOPES = DOMAINS + WRITE_SCOPES
SCOPE_PRESETS = {
    "job-agent": ["career", "calendar", "tasks", "career:write"],
    "full-read": list(DOMAINS),
    "full-access": list(ALL_SCOPES),
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
        "Athena is the user's personal life dashboard: calendar, tasks, finances, health, learning, habits, "
        "job hunt and Obsidian notes. Read with list_*/get_* tools; change data with the create/update/log/delete "
        "tools your token's scopes allow. Dates are YYYY-MM-DD and times are the user's local time "
        "('YYYY-MM-DD HH:MM'). Some of the user's data is private and is never shown to you; if something "
        "seems missing, don't guess at it. Prefer proposing a plan and confirming before bulk changes. "
        "log_application and add_lead are safe to repeat: duplicates are updated."
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




# --- Privacy filters (see privacy.py) -------------------------------------------

def _not_private_file(conn, column="file_id"):
    """SQL clause (and params) excluding rows that came from a private file."""
    ids = sorted(privacy.private_file_ids(conn))
    if not ids:
        return "1 = 1", []
    return f"({column} IS NULL OR {column} NOT IN ({','.join('?' * len(ids))}))", ids


def _not_private_task(column="source_file"):
    """SQL clause (and params) excluding tasks written inside a private note."""
    paths = sorted(privacy.private_note_paths())
    clause = f"({column} IS NULL OR ({column} NOT LIKE 'Private/%' AND {column} NOT LIKE '%/Private/%'"
    if paths:
        clause += f" AND {column} NOT IN ({','.join('?' * len(paths))})"
    return clause + "))", paths


def _visible_or_404(conn, table, row_id, what, file_column="file_id"):
    """Fetch a row an agent may touch; private rows look exactly like missing ones."""
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise ToolError(f"{what} {row_id} not found")
    if file_column and row[file_column] in privacy.private_file_ids(conn):
        raise ToolError(f"{what} {row_id} not found")
    return row


def _visible_task_or_404(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None or privacy.task_is_private(row["source_file"], privacy.private_note_paths()):
        raise ToolError(f"Task {task_id} not found")
    return row


def _api(fn, *args, **kwargs):
    """Call a dashboard API handler from main.py so MCP writes follow the same code path
    (Google Calendar push, tasks.md sync, validation). HTTP errors become tool errors."""
    from fastapi import HTTPException
    try:
        return fn(*args, **kwargs)
    except HTTPException as e:
        raise ToolError(str(e.detail))


def _main():
    import main  # lazy: main imports this module
    return main


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
            tc, tp = _not_private_task()
            cur.execute(f"SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND {tc}", tp)
            pending = cur.fetchone()[0]
            out["tasks"] = {
                "pending": pending,
                "overdue": _rows(cur, f"SELECT id, title, due_date, priority FROM tasks WHERE status = 'pending' AND due_date < ? AND {tc} ORDER BY due_date", (today, *tp)),
                "due_today": _rows(cur, f"SELECT id, title, priority FROM tasks WHERE status = 'pending' AND due_date = ? AND {tc}", (today, *tp)),
            }
        fc, fp = _not_private_file(conn)
        if "finances" in scopes:
            cur.execute(f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND date LIKE ? AND {fc}", (f"{today[:7]}%", *fp))
            out["finances"] = {"spent_this_month": cur.fetchone()[0], "net_wealth": finance.net_wealth(finance.account_balances(cur))}
        if "health" in scopes:
            latest = _rows(cur, f"SELECT * FROM health_logs WHERE {fc} ORDER BY date DESC LIMIT 1", fp)
            cur.execute(f"SELECT COUNT(*) FROM fitness_logs WHERE date >= ? AND {fc}", (week_ago, *fp))
            out["health"] = {"latest_vitals": latest[0] if latest else None, "workouts_last_7_days": cur.fetchone()[0]}
        if "habits" in scopes:
            out["habits_today"] = _rows(cur, "SELECT habit_name, completed FROM habit_logs WHERE date = ?", (today,))
        if "learning" in scopes:
            cur.execute(f"SELECT COALESCE(SUM(hours_spent), 0) FROM learning_progress WHERE date >= ? AND {fc}", (week_ago, *fp))
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
    events = _rows(conn.cursor(), """SELECT id, title, description, start_time, end_time, source, tags, color FROM calendar_events
        WHERE start_time <= ? AND end_time >= ? ORDER BY start_time LIMIT ?""",
                   (f"{end} 23:59:59", f"{start} 00:00:00", _limit(limit)))
    for ev in events:
        try:
            ev["tags"] = json.loads(ev["tags"]) if ev["tags"] else []
        except ValueError:
            ev["tags"] = []
    return events


@athena_tool("calendar")
def find_free_time(conn, date: str, day_start: str = "08:00", day_end: str = "22:00") -> dict:
    """Free gaps (15+ minutes) between events on a date (YYYY-MM-DD) within day_start-day_end (HH:MM), each with unblocked pending tasks that fit."""
    _date(date, "date")
    result = _api(_main().get_calendar_gaps, date, day_start, day_end)
    tc_paths = privacy.private_note_paths()
    for gap in result.get("gaps", []):
        gap["recommended_tasks"] = [
            {k: t.get(k) for k in ("id", "title", "priority", "due_date", "estimated_minutes", "category")}
            for t in gap.get("recommended_tasks", []) if not privacy.task_is_private(t.get("source_file"), tc_paths)
        ]
    return result


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
    tc, tp = _not_private_task()
    clauses.append(tc)
    params.extend(tp)
    cur = conn.cursor()
    tasks = _rows(cur, f"""SELECT id, title, category, status, due_date, priority, importance, estimated_minutes,
        recurrence, completed_at, source_file, event_id FROM tasks WHERE {' AND '.join(clauses)}
        ORDER BY due_date IS NULL, due_date, id LIMIT ?""", (*params, _limit(limit)))
    for t in tasks:
        t["subtasks"] = _rows(cur, "SELECT id, title, is_completed FROM task_subtasks WHERE task_id = ? ORDER BY position, id", (t["id"],))
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
    fc, fp = _not_private_file(conn, "t.file_id")
    clauses.append(fc)
    params.extend(fp)
    return _rows(conn.cursor(), f"""SELECT t.id, t.date, t.amount, t.type, t.category, t.merchant, t.description,
        t.account_id, a.name AS account_name, t.transfer_account_id FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id WHERE {' AND '.join(clauses)} ORDER BY t.date DESC, t.id DESC LIMIT ?""",
                 (*params, _limit(limit)))


@athena_tool("finances")
def get_finance_summary(conn) -> dict:
    """Account balances, net wealth, this month's spending by category vs. budgets, recurring payments, student loans.
    Balances include every transaction; per-transaction detail from private files is never shown."""
    cur = conn.cursor()
    accounts = finance.account_balances(cur)
    month = datetime.now().strftime("%Y-%m")
    fc, fp = _not_private_file(conn)
    return {
        "accounts": accounts,
        "net_wealth": finance.net_wealth(accounts),
        "month": month,
        "spending_by_category": _rows(cur, f"""SELECT category, SUM(amount) AS total FROM transactions
            WHERE type = 'expense' AND date LIKE ? AND {fc} GROUP BY category ORDER BY total DESC""", (f"{month}%", *fp)),
        "budgets": finance.load_budgets(),
        "recurring": _rows(cur, """SELECT r.id, r.name, r.amount, r.interval, r.category, r.account_id, r.next_due_date,
            a.name AS account_name FROM recurring_transactions r LEFT JOIN accounts a ON r.account_id = a.id
            WHERE r.active = 1 ORDER BY r.next_due_date"""),
        "student_loans": _rows(cur, "SELECT * FROM student_loans ORDER BY name"),
    }


HEALTH_KINDS = {
    "vitals": "health_logs",
    "fitness": "fitness_logs",
    "meals": "meal_logs",
    "mindfulness": "mindfulness_logs",
}
_FILE_LINKED = {"health_logs", "fitness_logs", "learning_progress", "transactions"}


@athena_tool("health")
def list_health_logs(conn, kind: str = "vitals", start_date: Optional[str] = None,
                     end_date: Optional[str] = None, limit: int = 60) -> dict:
    """Health records, newest first. kind: 'vitals' (weight, sleep, mood, BP, water, energy, stress), 'fitness', 'meals' or 'mindfulness'."""
    table = HEALTH_KINDS.get(kind)
    if not table:
        raise ToolError(f"kind must be one of {', '.join(HEALTH_KINDS)}")
    clauses, params = ["1 = 1"], []
    _where(clauses, params, "date", ">=", _date(start_date, "start_date"))
    _where(clauses, params, "date", "<=", _date(end_date, "end_date"))
    if table in _FILE_LINKED:
        fc, fp = _not_private_file(conn)
        clauses.append(fc)
        params.extend(fp)
    return _rows(conn.cursor(), f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY date DESC, id DESC LIMIT ?",
                 (*params, _limit(limit)))


@athena_tool("learning")
def list_learning(conn, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> dict:
    """Learning log entries (topic, category, hours, notes), newest first."""
    clauses, params = [], []
    _where(clauses, params, "date", ">=", _date(start_date, "start_date"))
    _where(clauses, params, "date", "<=", _date(end_date, "end_date"))
    fc, fp = _not_private_file(conn)
    clauses.append(fc)
    params.extend(fp)
    return _rows(conn.cursor(), f"SELECT * FROM learning_progress WHERE {' AND '.join(clauses)} ORDER BY date DESC, id DESC LIMIT ?",
                 (*params, _limit(limit)))


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


def _vault_path(relative_path, allow_private_folder=False):
    """Resolve a note path inside an allowed vault folder, or raise ToolError."""
    vault = os.path.realpath(agent.VAULT_DIR)
    full = os.path.realpath(os.path.join(vault, relative_path or ""))
    rel = os.path.relpath(full, vault)
    top = rel.split(os.sep, 1)[0]
    allowed = NOTE_FOLDERS + ((privacy.PRIVATE_FOLDER,) if allow_private_folder else ())
    if rel.startswith("..") or top not in allowed:
        raise ToolError(f"Notes must be inside one of: {', '.join(NOTE_FOLDERS)}")
    return full, rel.replace(os.sep, "/")


def _readable_note(path):
    """A note an agent may read or change: exists, markdown, and not private (private looks missing)."""
    full, rel = _vault_path(path)
    if not full.endswith(".md") or not os.path.isfile(full) or privacy.is_private_note(rel):
        raise ToolError(f"No note at {path}")
    return full, rel


@athena_tool("notes")
def list_notes(conn, folder: Optional[str] = None) -> dict:
    """Markdown notes in the Obsidian vault (daily briefs, summaries, projects, areas, resources, archives). folder: e.g. 'Daily_Briefs' or '02_Areas/Career'."""
    roots = [_vault_path(folder)[0]] if folder else [os.path.join(os.path.realpath(agent.VAULT_DIR), f) for f in NOTE_FOLDERS]
    vault = os.path.realpath(agent.VAULT_DIR)
    notes = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != privacy.PRIVATE_FOLDER]
            for f in filenames:
                if f.endswith(".md") and not f.startswith("."):
                    full = os.path.join(dirpath, f)
                    rel = os.path.relpath(full, vault).replace(os.sep, "/")
                    if privacy.is_private_note(rel):
                        continue
                    notes.append({
                        "path": rel,
                        "modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M:%S"),
                    })
    return sorted(notes, key=lambda n: n["path"])[:MAX_ROWS * 4]


@athena_tool("notes")
def read_note(conn, path: str) -> dict:
    """Read one markdown note by its vault path from list_notes (e.g. 'Daily_Briefs/Daily_Brief_2026-10-16.md')."""
    full, rel = _readable_note(path)
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = privacy.strip_private_lines(f.read(MAX_NOTE_CHARS + 1))
    return {"path": rel, "content": content[:MAX_NOTE_CHARS], "truncated": len(content) > MAX_NOTE_CHARS}


# --- Task write tools ---------------------------------------------------------

@athena_tool("tasks:write")
def create_task(conn, title: str, due_date: Optional[str] = None, priority: str = "medium", importance: str = "minor",
                estimated_minutes: int = 30, category: str = "general", recurrence: str = "none",
                event_id: Optional[int] = None, subtasks: Optional[list[str]] = None) -> dict:
    """Create a task (shows in the dashboard and tasks.md). priority: high/medium/low; importance: major/minor;
    recurrence: none/daily/weekly/monthly; due_date YYYY-MM-DD; event_id attaches it to a calendar event."""
    _date(due_date, "due_date")
    m = _main()
    return _api(m.add_task, m.TaskCreate(title=title, due_date=due_date, priority=priority, importance=importance,
                                         estimated_minutes=estimated_minutes, category=category, recurrence=recurrence,
                                         event_id=event_id, subtasks=subtasks))


@athena_tool("tasks:write")
def update_task(conn, task_id: int, title: Optional[str] = None, status: Optional[str] = None, due_date: Optional[str] = None,
                priority: Optional[str] = None, importance: Optional[str] = None, estimated_minutes: Optional[int] = None,
                category: Optional[str] = None, recurrence: Optional[str] = None, event_id: Optional[int] = None) -> dict:
    """Change a task. status: pending/completed (completing a task from a vault note ticks it in the note).
    Pass due_date "" to clear it and event_id 0 to detach it from its event."""
    _visible_task_or_404(conn, task_id)
    if due_date:
        _date(due_date, "due_date")
    m = _main()
    return _api(m.update_task, task_id, m.TaskUpdate(title=title, status=status, due_date=due_date, priority=priority,
                                                     importance=importance, estimated_minutes=estimated_minutes,
                                                     category=category, recurrence=recurrence, event_id=event_id))


@athena_tool("tasks:write")
def delete_task(conn, task_id: int) -> dict:
    """Delete a task and its subtasks."""
    _visible_task_or_404(conn, task_id)
    return _api(_main().delete_task, task_id)


@athena_tool("tasks:write")
def add_subtask(conn, task_id: int, title: str) -> dict:
    """Add a checklist item to a task."""
    _visible_task_or_404(conn, task_id)
    m = _main()
    return _api(m.add_subtask, task_id, m.SubtaskCreate(title=title))


@athena_tool("tasks:write")
def update_subtask(conn, task_id: int, subtask_id: int, title: Optional[str] = None, is_completed: Optional[bool] = None) -> dict:
    """Rename or tick/untick a subtask."""
    _visible_task_or_404(conn, task_id)
    m = _main()
    return _api(m.update_subtask, task_id, subtask_id, m.SubtaskUpdate(title=title, is_completed=is_completed))


@athena_tool("tasks:write")
def delete_subtask(conn, task_id: int, subtask_id: int) -> dict:
    """Remove a subtask."""
    _visible_task_or_404(conn, task_id)
    return _api(_main().delete_subtask, task_id, subtask_id)


# --- Calendar write tools -----------------------------------------------------

@athena_tool("calendar:write")
def create_event(conn, title: str, start_time: str, end_time: str, description: Optional[str] = None,
                 tags: Optional[list[str]] = None, color: Optional[str] = None, sync_to_google: bool = True) -> dict:
    """Create a calendar event. Times are local 'YYYY-MM-DD HH:MM'. By default it is also added to Google Calendar
    (if Google is unavailable it is saved locally and pushed on the next sync)."""
    m = _main()
    return _api(m.add_calendar_event, m.CalendarEventCreate(title=title, description=description, start_time=start_time,
                                                            end_time=end_time, tags=tags or [], color=color or "#4facfe",
                                                            sync_to_google=sync_to_google))


@athena_tool("calendar:write")
def update_event(conn, event_id: int, title: Optional[str] = None, start_time: Optional[str] = None,
                 end_time: Optional[str] = None, description: Optional[str] = None, tags: Optional[list[str]] = None,
                 color: Optional[str] = None) -> dict:
    """Change an event (Google-synced events are updated in Google first)."""
    m = _main()
    return _api(m.update_calendar_event, event_id, m.CalendarEventUpdate(title=title, start_time=start_time, end_time=end_time,
                                                                         description=description, tags=tags, color=color))


@athena_tool("calendar:write")
def delete_event(conn, event_id: int) -> dict:
    """Delete an event (also from Google Calendar when it came from there). Attached tasks are kept and detached."""
    return _api(_main().delete_calendar_event, event_id)


# --- Finance write tools ------------------------------------------------------

@athena_tool("finances:write")
def add_transaction(conn, date: str, amount: float, type: str, category: str, merchant: Optional[str] = None,
                    description: Optional[str] = None, account_id: Optional[int] = None,
                    transfer_account_id: Optional[int] = None) -> dict:
    """Record a transaction. type: expense/income/transfer (amount is always positive; transfers need transfer_account_id).
    Without account_id it goes to the default checking account."""
    _date(date, "date")
    m = _main()
    return _api(m.add_transaction, m.TransactionCreate(date=date, amount=amount, type=type, category=category, merchant=merchant,
                                                       description=description, account_id=account_id,
                                                       transfer_account_id=transfer_account_id))


@athena_tool("finances:write")
def update_transaction(conn, transaction_id: int, date: Optional[str] = None, amount: Optional[float] = None,
                       type: Optional[str] = None, category: Optional[str] = None, merchant: Optional[str] = None,
                       description: Optional[str] = None, account_id: Optional[int] = None,
                       transfer_account_id: Optional[int] = None) -> dict:
    """Change fields of a transaction."""
    _visible_or_404(conn, "transactions", transaction_id, "Transaction")
    _date(date, "date")
    if type is not None and type not in ("expense", "income", "transfer"):
        raise ToolError("type must be expense, income or transfer")
    return _update_row(conn, "transactions", transaction_id, dict(date=date, amount=amount, type=type, category=category,
                       merchant=merchant, description=description, account_id=account_id, transfer_account_id=transfer_account_id))


@athena_tool("finances:write")
def delete_transaction(conn, transaction_id: int) -> dict:
    """Delete a transaction."""
    _visible_or_404(conn, "transactions", transaction_id, "Transaction")
    return _api(_main().delete_transaction, transaction_id)


@athena_tool("finances:write")
def add_account(conn, name: str, type: str, starting_balance: float = 0.0) -> dict:
    """Add an account. type: checking/savings/credit_card/investment/cash (credit cards: negative balance = owed)."""
    m = _main()
    return _api(m.add_account, m.AccountCreate(name=name, type=type, starting_balance=starting_balance))


@athena_tool("finances:write")
def update_account(conn, account_id: int, name: Optional[str] = None, type: Optional[str] = None,
                   starting_balance: Optional[float] = None) -> dict:
    """Rename an account or correct its type / starting balance. (Accounts can't be deleted through MCP.)"""
    _visible_or_404(conn, "accounts", account_id, "Account", file_column=None)
    return _update_row(conn, "accounts", account_id, dict(name=name, type=type, starting_balance=starting_balance))


@athena_tool("finances:write")
def add_recurring(conn, name: str, amount: float, interval: str, category: str, account_id: int, next_due_date: str) -> dict:
    """Add a recurring payment. interval: weekly/monthly/yearly; next_due_date YYYY-MM-DD."""
    _date(next_due_date, "next_due_date")
    m = _main()
    return _api(m.add_recurring, m.RecurringCreate(name=name, amount=amount, interval=interval, category=category,
                                                   account_id=account_id, next_due_date=next_due_date))


@athena_tool("finances:write")
def update_recurring(conn, recurring_id: int, name: Optional[str] = None, amount: Optional[float] = None,
                     interval: Optional[str] = None, category: Optional[str] = None, account_id: Optional[int] = None,
                     next_due_date: Optional[str] = None, active: Optional[bool] = None) -> dict:
    """Change a recurring payment (active=false pauses it)."""
    _visible_or_404(conn, "recurring_transactions", recurring_id, "Recurring payment", file_column=None)
    _date(next_due_date, "next_due_date")
    return _update_row(conn, "recurring_transactions", recurring_id, dict(
        name=name, amount=amount, interval=interval, category=category, account_id=account_id,
        next_due_date=next_due_date, active=None if active is None else int(active)))


@athena_tool("finances:write")
def pay_recurring(conn, recurring_id: int) -> dict:
    """Record today's payment of a recurring item as an expense and move its due date forward."""
    return _api(_main().pay_recurring, recurring_id)


@athena_tool("finances:write")
def delete_recurring(conn, recurring_id: int) -> dict:
    """Delete a recurring payment (past transactions are kept)."""
    _visible_or_404(conn, "recurring_transactions", recurring_id, "Recurring payment", file_column=None)
    return _api(_main().delete_recurring, recurring_id)


@athena_tool("finances:write")
def save_student_loan(conn, name: str, type: Optional[str] = None, balance: Optional[float] = None,
                      interest_rate: Optional[float] = None, interest_accumulated: Optional[float] = None,
                      loan_id: Optional[int] = None) -> dict:
    """Add a student loan (type: subsidized/unsubsidized), or update one when loan_id is given. (No deletes through MCP.)"""
    m = _main()
    if loan_id is None:
        return _api(m.add_student_loan, m.StudentLoanCreate(name=name, type=type or "unsubsidized", balance=balance or 0.0,
                                                            interest_rate=interest_rate or 0.0,
                                                            interest_accumulated=interest_accumulated or 0.0))
    return _api(m.update_student_loan, loan_id, m.StudentLoanUpdate(name=name, type=type, balance=balance,
                                                                    interest_rate=interest_rate,
                                                                    interest_accumulated=interest_accumulated))


def _update_row(conn, table, row_id, fields):
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return {"id": row_id, "status": "no_change"}
    columns = ", ".join(f"{k} = ?" for k in fields)
    try:
        conn.execute(f"UPDATE {table} SET {columns} WHERE id = ?", (*fields.values(), row_id))
    except sqlite3.IntegrityError as e:
        raise ToolError(f"Invalid value: {e}")
    return {"id": row_id, "status": "success", "updated": sorted(fields)}


# --- Health, learning and habit write tools -----------------------------------

@athena_tool("health:write")
def log_vitals(conn, date: str, weight_lbs: Optional[float] = None, sleep_hours: Optional[float] = None,
               mood: Optional[str] = None, systolic: Optional[int] = None, diastolic: Optional[int] = None,
               water_ml: Optional[int] = None, energy_level: Optional[int] = None, stress_level: Optional[int] = None,
               notes: Optional[str] = None) -> dict:
    """Record the day's vitals. Only the fields you pass change; the rest of that day's entry is kept.
    mood/energy/stress are 1-10."""
    _date(date, "date")
    existing = conn.execute("SELECT id, file_id FROM health_logs WHERE date = ?", (date,)).fetchone()
    if existing and existing["file_id"] in privacy.private_file_ids(conn):
        raise ToolError(f"The {date} vitals entry is private and can only be changed on the Athena machine.")
    fields = {k: v for k, v in dict(weight_lbs=weight_lbs, sleep_hours=sleep_hours, mood=mood, systolic=systolic,
              diastolic=diastolic, water_ml=water_ml, energy_level=energy_level, stress_level=stress_level,
              notes=notes).items() if v is not None}
    if not fields:
        raise ToolError("Pass at least one vital to record.")
    if existing:
        return _update_row(conn, "health_logs", existing["id"], fields)
    columns = ", ".join(["date", *fields])
    conn.execute(f"INSERT INTO health_logs ({columns}) VALUES ({','.join('?' * (len(fields) + 1))})", (date, *fields.values()))
    return {"status": "success", "date": date, "recorded": sorted(fields)}


@athena_tool("health:write")
def log_workout(conn, date: str, activity_type: str, duration_minutes: int, intensity: str = "medium",
                distance_km: Optional[float] = None, calories_burned: Optional[int] = None, notes: Optional[str] = None) -> dict:
    """Record a workout. activity_type: run/lift/cycle/swim/yoga/other (free text ok); intensity: low/medium/high."""
    _date(date, "date")
    m = _main()
    return _api(m.add_fitness, m.FitnessLogCreate(date=date, activity_type=activity_type, duration_minutes=duration_minutes,
                                                  distance_km=distance_km, calories_burned=calories_burned,
                                                  intensity=intensity, notes=notes))


@athena_tool("health:write")
def log_meal(conn, date: str, meal_type: str, description: str, calories: Optional[int] = None,
             protein_g: Optional[float] = None, carbs_g: Optional[float] = None, fat_g: Optional[float] = None) -> dict:
    """Record a meal. meal_type: breakfast/lunch/dinner/snack."""
    _date(date, "date")
    m = _main()
    return _api(m.add_meal, m.MealLogCreate(date=date, meal_type=meal_type, description=description, calories=calories,
                                            protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g))


@athena_tool("health:write")
def log_mindfulness(conn, date: str, activity_type: str, duration_minutes: int, notes: Optional[str] = None) -> dict:
    """Record a mindfulness session (meditation, breathing, journaling, ...)."""
    _date(date, "date")
    m = _main()
    return _api(m.add_mindfulness, m.MindfulnessLogCreate(date=date, activity_type=activity_type,
                                                          duration_minutes=duration_minutes, notes=notes))


@athena_tool("health:write")
def delete_health_entry(conn, kind: str, entry_id: int) -> dict:
    """Delete one health record. kind: vitals/fitness/meals/mindfulness; entry_id from list_health_logs."""
    table = HEALTH_KINDS.get(kind)
    if not table:
        raise ToolError(f"kind must be one of {', '.join(HEALTH_KINDS)}")
    _visible_or_404(conn, table, entry_id, "Entry", file_column="file_id" if table in _FILE_LINKED else None)
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (entry_id,))
    return {"status": "success", "kind": kind, "id": entry_id}


@athena_tool("learning:write")
def log_learning(conn, date: str, topic: str, category: str, hours_spent: float, notes: Optional[str] = None,
                 source_link: Optional[str] = None, status: str = "completed") -> dict:
    """Record study time. status: completed/in-progress."""
    _date(date, "date")
    m = _main()
    return _api(m.add_learning, m.LearningProgressCreate(date=date, topic=topic, category=category, hours_spent=hours_spent,
                                                         notes=notes, source_link=source_link, status=status))


@athena_tool("learning:write")
def delete_learning_entry(conn, entry_id: int) -> dict:
    """Delete a learning log entry."""
    _visible_or_404(conn, "learning_progress", entry_id, "Entry")
    conn.execute("DELETE FROM learning_progress WHERE id = ?", (entry_id,))
    return {"status": "success", "id": entry_id}


@athena_tool("habits:write")
def log_habit(conn, date: str, habit_name: str, completed: bool = True, notes: Optional[str] = None) -> dict:
    """Check a habit off (or mark it missed with completed=false) for a date. One entry per habit per day."""
    _date(date, "date")
    m = _main()
    return _api(m.add_habit_log, m.HabitLogCreate(date=date, habit_name=habit_name, completed=int(completed), notes=notes))


@athena_tool("habits:write")
def delete_habit_log(conn, date: str, habit_name: str) -> dict:
    """Remove a habit check-in for a date."""
    _date(date, "date")
    cur = conn.execute("DELETE FROM habit_logs WHERE date = ? AND habit_name = ?", (date, habit_name))
    if cur.rowcount == 0:
        raise ToolError(f"No '{habit_name}' check-in on {date}")
    return {"status": "success"}


# --- Note write tools ---------------------------------------------------------

def _after_note_change():
    """Pick up tasks written in notes (LLM-free sync), in the background."""
    import threading
    m = _main()
    threading.Thread(target=m.run_agent_in_background, args=(agent.run_light_sync,), daemon=True).start()


@athena_tool("notes:write")
def write_note(conn, path: str, content: str, overwrite: bool = False) -> dict:
    """Create a markdown note (e.g. '01_Projects/Trip.md'), or replace one with overwrite=true. Tasks written as
    '- [ ] ...' are picked up as Athena tasks. Writing inside 'Private/' (or with 'private: true' frontmatter)
    makes the note private: after that you can't read or change it."""
    full, rel = _vault_path(path, allow_private_folder=True)
    if not rel.endswith(".md"):
        raise ToolError("Notes must end in .md")
    exists = os.path.isfile(full)
    if exists and (privacy.is_private_note(rel) or not overwrite):
        raise ToolError(f"{path} already exists" + ("" if privacy.is_private_note(rel) else "; pass overwrite=true to replace it"))
    agent.write_file_atomically(full, content)
    _after_note_change()
    return {"status": "success", "path": rel, "created": not exists, "private": privacy.is_private_note(rel)}


@athena_tool("notes:write")
def append_to_note(conn, path: str, text: str) -> dict:
    """Append text to the end of an existing note."""
    full, rel = _readable_note(path)
    with open(full, "r", encoding="utf-8") as f:
        current = f.read()
    agent.write_file_atomically(full, current.rstrip("\n") + "\n\n" + text.strip("\n") + "\n")
    _after_note_change()
    return {"status": "success", "path": rel}


@athena_tool("notes:write")
def delete_note(conn, path: str) -> dict:
    """Delete a note."""
    full, rel = _readable_note(path)
    os.remove(full)
    _after_note_change()
    return {"status": "success", "path": rel}


@athena_tool("notes:write")
def mark_note_private(conn, path: str) -> dict:
    """Make a note private (adds 'private: true'). Private notes and anything derived from them are hidden from
    every cloud model, including you, from now on. Only the user can undo this, on the Athena machine."""
    full, rel = _readable_note(path)
    privacy.set_note_private(rel, True)
    _after_note_change()
    return {"status": "success", "path": rel, "private": True}


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
def update_application(conn, application_id: int, company: Optional[str] = None, role: Optional[str] = None,
                       date_applied: Optional[str] = None, job_url: Optional[str] = None,
                       salary_range: Optional[str] = None, notes: Optional[str] = None,
                       recruiter_name: Optional[str] = None, recruiter_email: Optional[str] = None) -> dict:
    """Edit an application's details (use update_application_status for status)."""
    career.update_application(conn, application_id, dict(
        company=company, role=role, date_applied=date_applied, job_description_url=job_url, salary_range=salary_range,
        notes=notes, recruiter_name=recruiter_name, recruiter_email=recruiter_email), created_by=_agent_name())
    return {"id": application_id, "status": "success"}


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
def delete_application(conn, application_id: int) -> dict:
    """Delete an application and its timeline."""
    career.delete_application(conn, application_id)
    return {"id": application_id, "status": "deleted"}


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
