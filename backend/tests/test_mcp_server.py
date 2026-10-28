import json
import os
import sys
from datetime import date, timedelta

import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent
import database
import main
import mcp_server
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "mcp.db"))
    vault = tmp_path / "vault"
    (vault / "Daily_Briefs").mkdir(parents=True)
    (vault / "Daily_Briefs" / "Daily_Brief_2026-10-16.md").write_text("# Brief\nGym at 7")
    (vault / "Inbox").mkdir()
    (vault / "Inbox" / "secret.md").write_text("unprocessed")
    monkeypatch.setattr(agent, "VAULT_DIR", str(vault))
    monkeypatch.setattr(mcp_server, "rate_limiter", mcp_server.RateLimiter(1000))
    database.init_db()
    yield


@pytest.fixture
def client():
    with TestClient(main.app) as c:  # runs the lifespan, which starts the MCP session manager
        yield c


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def call(client, token, tool, **arguments):
    res = client.post("/mcp", headers=_headers(token), json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments},
    })
    assert res.status_code == 200, res.text
    result = res.json()["result"]
    text = result["content"][0]["text"] if result["content"] else ""
    if result["isError"]:
        return {"error": text}
    data = json.loads(text)
    return data["items"] if set(data) == {"count", "items"} else data


def test_requires_valid_token(client):
    assert client.post("/mcp", json={}).status_code == 401
    assert client.post("/mcp", headers=_headers("ath_nope"), json={}).status_code == 401
    token = mcp_server.create_token("temp", ["career"])
    assert mcp_server.revoke_token("temp")
    assert client.post("/mcp", headers=_headers(token), json={}).status_code == 401


def test_tools_listed_without_conn_param(client):
    token = mcp_server.create_token("agent", ["career"])
    res = client.post("/mcp", headers=_headers(token), json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in res.json()["result"]["tools"]}
    assert {"get_overview", "log_application", "read_note", "list_transactions"} <= set(tools)
    assert "conn" not in tools["log_application"]["inputSchema"]["properties"]
    assert tools["log_application"]["inputSchema"]["required"] == ["company", "role"]


def test_scopes_are_enforced_and_logged(client):
    token = mcp_server.create_token("job", mcp_server.SCOPE_PRESETS["job-agent"])
    reader = mcp_server.create_token("reader", ["finances"])
    assert "finances" in call(client, token, "list_transactions")["error"]
    assert "career:write" in call(client, reader, "log_application", company="A", role="B")["error"]
    assert isinstance(call(client, reader, "list_transactions"), list)

    overview = call(client, reader, "get_overview")
    assert "finances" in overview and "career" not in overview and "tasks" not in overview

    conn = database.create_new_connection()
    try:
        rows = conn.execute("SELECT token_name, tool, ok FROM mcp_call_log ORDER BY id").fetchall()
    finally:
        conn.close()
    assert [tuple(r) for r in rows] == [
        ("job", "list_transactions", 0), ("reader", "log_application", 0),
        ("reader", "list_transactions", 1), ("reader", "get_overview", 1),
    ]


def test_career_writes_record_agent(client):
    token = mcp_server.create_token("claude-cloud", mcp_server.SCOPE_PRESETS["job-agent"])
    created = call(client, token, "log_application", company="Acme", role="SWE", job_url="https://acme.jobs/1")
    assert created["result"] == "created"
    assert call(client, token, "log_application", company="acme", role="swe")["result"] == "updated"
    call(client, token, "update_application_status", application_id=created["id"], status="interviewing", note="screen")
    call(client, token, "add_application_event", application_id=created["id"], kind="interview",
         event_date=(date.today() + timedelta(days=7)).isoformat())
    assert "update_application_status" in call(client, token, "add_application_event",
                                               application_id=created["id"], kind="status_change")["error"]

    app = call(client, token, "get_application", application_id=created["id"])
    assert app["created_by"] == "claude-cloud"
    assert [e["kind"] for e in app["events"]] == ["status_change", "status_change", "interview"]
    assert {e["created_by"] for e in app["events"]} == {"claude-cloud"}

    lead = call(client, token, "add_lead", company="Beta", role="SRE", job_url="https://beta.jobs/2", match_score=80)
    assert call(client, token, "list_leads")[0]["source"] == "claude-cloud"
    promoted = call(client, token, "promote_lead", lead_id=lead["id"])
    assert call(client, token, "list_leads") == []
    assert call(client, token, "get_application", application_id=promoted["id"])["lead_id"] == lead["id"]
    assert "not found" in call(client, token, "dismiss_lead", lead_id=999)["error"]


def test_read_tools_return_domain_data(client):
    token = mcp_server.create_token("all", list(mcp_server.DOMAINS))
    client.post("/api/finances", json={"date": "2026-10-10", "amount": 12.5, "type": "expense", "category": "food"})
    client.post("/api/tasks", json={"title": "Write cover letter", "due_date": "2026-10-18", "subtasks": ["draft"]})
    client.post("/api/calendar", json={"title": "Interview", "start_time": "2026-10-20 10:00",
                                       "end_time": "2026-10-20 11:00", "sync_to_google": False})

    assert call(client, token, "list_transactions", start_date="2026-10-01")[0]["amount"] == 12.5
    assert "net_wealth" in call(client, token, "get_finance_summary")
    task = call(client, token, "list_tasks", due_before="2026-10-31")[0]
    assert task["title"] == "Write cover letter" and task["subtasks"][0]["title"] == "draft"
    assert call(client, token, "list_events", start_date="2026-10-20", end_date="2026-10-20")[0]["title"] == "Interview"
    assert "kind must be" in call(client, token, "list_health_logs", kind="dreams")["error"]
    assert "YYYY-MM-DD" in call(client, token, "list_transactions", start_date="last week")["error"]


def test_notes_are_confined_to_allowed_folders(client):
    token = mcp_server.create_token("notes", ["notes"])
    notes = call(client, token, "list_notes")
    assert [n["path"] for n in notes] == ["Daily_Briefs/Daily_Brief_2026-10-16.md"]
    assert call(client, token, "read_note", path="Daily_Briefs/Daily_Brief_2026-10-16.md")["content"].startswith("# Brief")
    for bad in ["Inbox/secret.md", "../../etc/passwd", "Daily_Briefs/../Inbox/secret.md", "/etc/passwd"]:
        assert "error" in call(client, token, "read_note", path=bad), bad


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(mcp_server, "rate_limiter", mcp_server.RateLimiter(2))
    token = mcp_server.create_token("busy", ["career"])
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert [client.post("/mcp", headers=_headers(token), json=body).status_code for _ in range(3)] == [200, 200, 429]


def test_token_validation():
    with pytest.raises(ValueError):
        mcp_server.create_token("x", ["career:delete"])
    with pytest.raises(ValueError):
        mcp_server.create_token("x", [])
    token = mcp_server.create_token("dup", ["career"])
    assert token.startswith("ath_")
    conn = database.create_new_connection()
    try:
        stored = conn.execute("SELECT token_hash FROM mcp_tokens WHERE name = 'dup'").fetchone()[0]
    finally:
        conn.close()
    assert stored == mcp_server.hash_token(token) and token not in stored
