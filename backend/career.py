"""
Career data: job applications, their event timeline, and job leads.

Shared by the REST API (main.py) and the MCP server (mcp_server.py), so both apply
the same validation and duplicate protection. Functions take an open connection and
leave committing to the caller.
"""
from datetime import datetime, timedelta

APPLICATION_STATUSES = ('applied', 'interviewing', 'offered', 'rejected', 'withdrawn')
EVENT_KINDS = ('status_change', 'interview', 'recruiter_contact', 'offer', 'note')
LEAD_STATUSES = ('lead', 'ignored', 'applied')

# An application to the same company + role within this many days counts as the same one.
DUPLICATE_WINDOW_DAYS = 90

# Fields of job_applications a caller may set directly.
APPLICATION_FIELDS = (
    'company', 'role', 'date_applied', 'job_description_url', 'salary_range',
    'notes', 'recruiter_name', 'recruiter_email',
)


class CareerError(ValueError):
    """Invalid input (maps to HTTP 400)."""


class CareerNotFound(CareerError):
    """The referenced application or lead does not exist (maps to HTTP 404)."""


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _check_date(value, field):
    if value is None:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        raise CareerError(f"{field} must be a date like YYYY-MM-DD, got {value!r}")


def _check_choice(value, allowed, field):
    if value not in allowed:
        raise CareerError(f"{field} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _required(value, field):
    if value is None or not str(value).strip():
        raise CareerError(f"{field} is required")
    return str(value).strip()


def _clean(value):
    """Strip strings; turn blank strings into None so they don't overwrite real data."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _normalize_url(url):
    url = _clean(url)
    return url.rstrip('/') if url else None


def _application_row(cursor, application_id):
    cursor.execute("SELECT * FROM job_applications WHERE id = ?", (application_id,))
    row = cursor.fetchone()
    if not row:
        raise CareerNotFound(f"Application {application_id} not found")
    return row


def _events_for(cursor, application_id):
    cursor.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date ASC, id ASC",
        (application_id,)
    )
    return [dict(r) for r in cursor.fetchall()]


# --- Applications -------------------------------------------------------------

def list_applications(conn, status=None, limit=200, include_events=False):
    cursor = conn.cursor()
    if status is not None:
        _check_choice(status, APPLICATION_STATUSES, "status")
        cursor.execute(
            "SELECT * FROM job_applications WHERE status = ? ORDER BY date_applied DESC, id DESC LIMIT ?",
            (status, limit)
        )
    else:
        cursor.execute("SELECT * FROM job_applications ORDER BY date_applied DESC, id DESC LIMIT ?", (limit,))
    apps = [dict(r) for r in cursor.fetchall()]
    if include_events:
        for app in apps:
            app['events'] = _events_for(cursor, app['id'])
    return apps


def get_application(conn, application_id):
    cursor = conn.cursor()
    app = dict(_application_row(cursor, application_id))
    app['events'] = _events_for(cursor, application_id)
    return app


def add_application_event(conn, application_id, kind, note=None, event_date=None, created_by=None):
    cursor = conn.cursor()
    _application_row(cursor, application_id)
    _check_choice(kind, EVENT_KINDS, "kind")
    cursor.execute(
        "INSERT INTO application_events (application_id, event_date, kind, note, created_by) VALUES (?, ?, ?, ?, ?)",
        (application_id, _check_date(event_date, "event_date") or _today(), kind, _clean(note), created_by)
    )
    return cursor.lastrowid


def find_duplicate_application(conn, company, role, job_url=None, date_applied=None):
    """Match on job URL first, then on company + role (case-insensitive) within DUPLICATE_WINDOW_DAYS."""
    cursor = conn.cursor()
    url = _normalize_url(job_url)
    if url:
        cursor.execute(
            "SELECT id FROM job_applications WHERE RTRIM(TRIM(job_description_url), '/') = ? ORDER BY id DESC LIMIT 1",
            (url,)
        )
        row = cursor.fetchone()
        if row:
            return row['id']
    anchor = datetime.strptime(date_applied or _today(), "%Y-%m-%d")
    lo = (anchor - timedelta(days=DUPLICATE_WINDOW_DAYS)).strftime("%Y-%m-%d")
    hi = (anchor + timedelta(days=DUPLICATE_WINDOW_DAYS)).strftime("%Y-%m-%d")
    cursor.execute(
        """SELECT id FROM job_applications
           WHERE LOWER(TRIM(company)) = LOWER(?) AND LOWER(TRIM(role)) = LOWER(?)
             AND date_applied BETWEEN ? AND ?
           ORDER BY date_applied DESC, id DESC LIMIT 1""",
        (company.strip(), role.strip(), lo, hi)
    )
    row = cursor.fetchone()
    return row['id'] if row else None


def set_application_status(conn, application_id, status, note=None, event_date=None, created_by=None):
    """Change status and record it on the timeline. Returns True if the status changed."""
    cursor = conn.cursor()
    row = _application_row(cursor, application_id)
    _check_choice(status, APPLICATION_STATUSES, "status")
    if row['status'] == status:
        if note:
            add_application_event(conn, application_id, 'note', note, event_date, created_by)
        return False
    cursor.execute("UPDATE job_applications SET status = ? WHERE id = ?", (status, application_id))
    text = f"{row['status']} → {status}"
    add_application_event(conn, application_id, 'status_change', f"{text}: {note}" if note else text, event_date, created_by)
    return True


def update_application(conn, application_id, fields, created_by=None):
    """
    Update the given fields (None values are ignored). A 'status' key goes through
    set_application_status so the change lands on the timeline.
    """
    cursor = conn.cursor()
    _application_row(cursor, application_id)
    fields = {k: _clean(v) for k, v in fields.items() if v is not None}
    status = fields.pop('status', None)
    unknown = set(fields) - set(APPLICATION_FIELDS)
    if unknown:
        raise CareerError(f"Unknown application fields: {', '.join(sorted(unknown))}")
    if 'date_applied' in fields:
        fields['date_applied'] = _check_date(fields['date_applied'], "date_applied")
    for key in ('company', 'role', 'date_applied'):
        if key in fields and not fields[key]:
            raise CareerError(f"{key} cannot be empty")
    fields = {k: v for k, v in fields.items() if v is not None}
    if fields:
        columns = ", ".join(f"{k} = ?" for k in fields)
        cursor.execute(f"UPDATE job_applications SET {columns} WHERE id = ?", (*fields.values(), application_id))
    if status is not None:
        set_application_status(conn, application_id, status, created_by=created_by)


def log_application(conn, company, role, date_applied=None, job_url=None, status=None,
                    salary_range=None, notes=None, recruiter_name=None, recruiter_email=None,
                    lead_id=None, created_by=None):
    """
    Record an application, or update the existing one if it is a duplicate
    (see find_duplicate_application). Returns {"id", "result": "created" | "updated"}.
    status defaults to 'applied' for a new application; for a duplicate it only changes
    when passed, so re-logging never moves an application backwards.
    """
    company = _required(company, "company")
    role = _required(role, "role")
    date_applied = _check_date(date_applied, "date_applied") or _today()
    if status is not None:
        _check_choice(status, APPLICATION_STATUSES, "status")
    job_url = _normalize_url(job_url)

    existing_id = find_duplicate_application(conn, company, role, job_url, date_applied)
    if existing_id:
        update_application(conn, existing_id, {
            'job_description_url': job_url, 'salary_range': salary_range, 'notes': notes,
            'recruiter_name': recruiter_name, 'recruiter_email': recruiter_email, 'status': status,
        }, created_by=created_by)
        if lead_id is not None:
            conn.execute("UPDATE job_applications SET lead_id = COALESCE(lead_id, ?) WHERE id = ?", (lead_id, existing_id))
        return {"id": existing_id, "result": "updated"}

    status = status or 'applied'
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO job_applications
           (date_applied, company, role, salary_range, status, job_description_url, notes,
            lead_id, recruiter_name, recruiter_email, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date_applied, company, role, _clean(salary_range), status, job_url, _clean(notes),
         lead_id, _clean(recruiter_name), _clean(recruiter_email), created_by)
    )
    app_id = cursor.lastrowid
    add_application_event(conn, app_id, 'status_change', f"Logged as {status}", date_applied, created_by)
    return {"id": app_id, "result": "created"}


def delete_application(conn, application_id):
    cursor = conn.cursor()
    _application_row(cursor, application_id)
    cursor.execute("DELETE FROM application_events WHERE application_id = ?", (application_id,))
    cursor.execute("DELETE FROM job_applications WHERE id = ?", (application_id,))


# --- Leads --------------------------------------------------------------------

def _lead_row(cursor, lead_id):
    cursor.execute("SELECT * FROM job_leads WHERE id = ?", (lead_id,))
    row = cursor.fetchone()
    if not row:
        raise CareerNotFound(f"Lead {lead_id} not found")
    return row


def list_leads(conn, status='lead', limit=200):
    cursor = conn.cursor()
    if status is not None:
        _check_choice(status, LEAD_STATUSES, "status")
        cursor.execute(
            "SELECT * FROM job_leads WHERE status = ? ORDER BY match_score DESC, date_found DESC, id DESC LIMIT ?",
            (status, limit)
        )
    else:
        cursor.execute("SELECT * FROM job_leads ORDER BY date_found DESC, id DESC LIMIT ?", (limit,))
    return [dict(r) for r in cursor.fetchall()]


def add_lead(conn, company, role, job_url, location=None, salary_range=None, description=None,
             source='agent', is_remote=False, match_score=None, created_by=None):
    """Add a lead, or update the one with the same job URL. Returns {"id", "result": "created" | "updated"}."""
    company = _required(company, "company")
    role = _required(role, "role")
    job_url = _normalize_url(_required(job_url, "job_url"))
    if match_score is not None and not (0 <= int(match_score) <= 100):
        raise CareerError("match_score must be between 0 and 100")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM job_leads WHERE RTRIM(TRIM(job_url), '/') = ?", (job_url,))
    row = cursor.fetchone()
    if row:
        updates = {
            'company': company, 'role': role, 'location': _clean(location), 'salary_range': _clean(salary_range),
            'job_description': _clean(description), 'is_remote': int(bool(is_remote)),
            'match_score': match_score,
        }
        updates = {k: v for k, v in updates.items() if v is not None}
        columns = ", ".join(f"{k} = ?" for k in updates)
        cursor.execute(f"UPDATE job_leads SET {columns} WHERE id = ?", (*updates.values(), row['id']))
        return {"id": row['id'], "result": "updated"}
    cursor.execute(
        """INSERT INTO job_leads
           (date_found, company, role, location, salary_range, job_description, job_url, source,
            status, is_remote, tier, match_score, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'lead', ?, 1, ?, ?)""",
        (_today(), company, role, _clean(location), _clean(salary_range), _clean(description), job_url,
         _clean(source) or 'agent', int(bool(is_remote)), int(match_score or 0), created_by)
    )
    return {"id": cursor.lastrowid, "result": "created"}


def dismiss_lead(conn, lead_id):
    cursor = conn.cursor()
    _lead_row(cursor, lead_id)
    cursor.execute("UPDATE job_leads SET status = 'ignored' WHERE id = ?", (lead_id,))


def promote_lead(conn, lead_id, date_applied=None, notes=None, created_by=None):
    """Turn a lead into an application (linked by lead_id) and mark the lead applied."""
    cursor = conn.cursor()
    lead = _lead_row(cursor, lead_id)
    result = log_application(
        conn, lead['company'], lead['role'], date_applied=date_applied, job_url=lead['job_url'],
        salary_range=lead['salary_range'], notes=notes, lead_id=lead_id, created_by=created_by,
    )
    cursor.execute("UPDATE job_leads SET status = 'applied' WHERE id = ?", (lead_id,))
    return result


def career_stats(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) AS n FROM job_applications GROUP BY status")
    by_status = {s: 0 for s in APPLICATION_STATUSES}
    by_status.update({r['status']: r['n'] for r in cursor.fetchall()})
    cursor.execute("SELECT COUNT(*) FROM job_leads WHERE status = 'lead'")
    open_leads = cursor.fetchone()[0]
    return {
        "total_applications": sum(by_status.values()),
        "active_applications": by_status['applied'] + by_status['interviewing'],
        "by_status": by_status,
        "open_leads": open_leads,
    }
