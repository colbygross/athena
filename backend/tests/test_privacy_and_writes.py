import json
import os
import sys
from datetime import datetime

import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent
import database
import main
import mcp_server
import privacy
from fastapi.testclient import TestClient

TODAY = datetime.now().strftime("%Y-%m-%d")


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "p.db"))
    vault = tmp_path / "vault"
    (vault / "01_Projects").mkdir(parents=True)
    (vault / "Private").mkdir()
    (vault / "Daily_Briefs").mkdir()
    (vault / "01_Projects" / "Public.md").write_text(f"# Public\n- [ ] Public task 📅 {TODAY}\n")
    (vault / "01_Projects" / "Secret.md").write_text(f"---\nprivate: true\n---\n# Secret\n- [ ] Secret task 📅 {TODAY}\n")
    (vault / "Private" / "Diary.md").write_text("# Diary\n- [ ] Diary task\n")
    monkeypatch.setattr(agent, "VAULT_DIR", str(vault))
    monkeypatch.setattr(agent, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(mcp_server, "rate_limiter", mcp_server.RateLimiter(1000))
    monkeypatch.setattr(mcp_server, "_after_note_change", lambda: None)
    privacy._note_cache.clear()
    database.init_db()
    agent.reconcile_tasks_in_db(agent.scan_vault_for_tasks())

    conn = database.create_new_connection()
    pub = conn.execute("INSERT INTO processed_files (original_name, new_path, category) VALUES ('r1.png', 'storage/r1.png', 'finances')").lastrowid
    sec = conn.execute("INSERT INTO processed_files (original_name, new_path, category, private) VALUES ('r2.png', 'storage/r2.png', 'finances', 1)").lastrowid
    for fid, merchant in ((pub, "Cafe"), (sec, "Pharmacy"), (None, "Grocer")):
        conn.execute("INSERT INTO transactions (date, amount, type, category, merchant, account_id, file_id) VALUES (?, 10, 'expense', 'other', ?, 1, ?)",
                     (TODAY, merchant, fid))
    conn.execute("INSERT INTO health_logs (date, weight_lbs, file_id) VALUES ('2026-01-01', 150, ?)", (sec,))
    conn.execute("INSERT INTO health_logs (date, weight_lbs) VALUES ('2026-01-02', 151)")
    conn.commit()
    conn.close()
    yield


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def call(client, token, tool, **arguments):
    res = client.post("/mcp", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream", "Content-Type": "application/json",
    }, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    assert res.status_code == 200, res.text
    result = res.json()["result"]
    text = result["content"][0]["text"] if result["content"] else "{}"
    if result["isError"]:
        return {"error": text}
    data = json.loads(text)
    return data["items"] if isinstance(data, dict) and set(data) == {"count", "items"} else data


@pytest.fixture
def token():
    return mcp_server.create_token("all", mcp_server.SCOPE_PRESETS["full-access"])


def test_private_notes_are_invisible(client, token):
    paths = [n["path"] for n in call(client, token, "list_notes")]
    assert "01_Projects/Public.md" in paths
    assert "01_Projects/Secret.md" not in paths and not any(p.startswith("Private/") for p in paths)
    for path in ("01_Projects/Secret.md", "Private/Diary.md"):
        assert "error" in call(client, token, "read_note", path=path)
        assert "error" in call(client, token, "append_to_note", path=path, text="x")
        assert "error" in call(client, token, "delete_note", path=path)
    assert "error" in call(client, token, "write_note", path="01_Projects/Secret.md", content="pwned", overwrite=True)


def test_tasks_from_private_notes_are_hidden(client, token):
    titles = [t["title"] for t in call(client, token, "list_tasks")]
    assert titles == ["Public task"]
    assert [t["title"] for t in call(client, token, "get_overview")["tasks"]["due_today"]] == ["Public task"]
    conn = database.create_new_connection()
    secret_id = conn.execute("SELECT id FROM tasks WHERE title = 'Secret task'").fetchone()[0]
    conn.close()
    for tool, args in (("update_task", {"status": "completed"}), ("delete_task", {}), ("add_subtask", {"title": "x"})):
        assert "not found" in call(client, token, tool, task_id=secret_id, **args)["error"]


def test_rows_from_private_files_are_hidden(client, token):
    merchants = {t["merchant"] for t in call(client, token, "list_transactions")}
    assert merchants == {"Cafe", "Grocer"}
    summary = call(client, token, "get_finance_summary")
    assert summary["spending_by_category"] == [{"category": "other", "total": 20.0}]
    assert call(client, token, "get_overview")["finances"]["spent_this_month"] == 20.0
    vitals = call(client, token, "list_health_logs", kind="vitals")
    assert [v["date"] for v in vitals] == ["2026-01-02"]
    assert "private" in call(client, token, "log_vitals", date="2026-01-01", sleep_hours=8)["error"]

    conn = database.create_new_connection()
    private_tx = conn.execute("SELECT id FROM transactions WHERE merchant = 'Pharmacy'").fetchone()[0]
    conn.close()
    assert "not found" in call(client, token, "delete_transaction", transaction_id=private_tx)["error"]
    assert "not found" in call(client, token, "update_transaction", transaction_id=private_tx, amount=1)["error"]


def test_generated_notes_hide_private_lines_from_cloud_only(client, token):
    agent.generate_daily_brief(TODAY)
    raw = open(os.path.join(agent.VAULT_DIR, "Daily_Briefs", f"Daily_Brief_{TODAY}.md")).read()
    secret_line = next(l for l in raw.split("\n") if "Secret task" in l)
    assert privacy.PRIVATE_MARKER in secret_line

    cloud = call(client, token, "read_note", path=f"Daily_Briefs/Daily_Brief_{TODAY}.md")["content"]
    assert "Public task" in cloud and "Secret task" not in cloud and "Diary task" not in cloud

    local = client.get(f"/api/daily-briefs/{TODAY}").json()["content"]
    assert "Secret task" in local and privacy.PRIVATE_MARKER not in local


def test_agents_can_mark_private_but_not_unmark(client, token):
    assert call(client, token, "mark_note_private", path="01_Projects/Public.md")["private"] is True
    assert "No note" in call(client, token, "read_note", path="01_Projects/Public.md")["error"]
    assert call(client, token, "list_tasks") == []
    assert not any("unmark" in t or "unflag" in t for t in (x.name for x in mcp_server.mcp._tool_manager.list_tools()))

    # The local dashboard can undo it; folder-private notes stay private.
    assert client.post("/api/privacy", json={"path": "01_Projects/Public.md", "private": False}).json()["private"] is False
    assert "Public" in call(client, token, "read_note", path="01_Projects/Public.md")["content"]
    assert client.post("/api/privacy", json={"path": "Private/Diary.md", "private": False}).status_code == 400
    listing = client.get("/api/privacy").json()
    assert "Private/Diary.md" in listing["private_notes"] and listing["private_files"][0]["original_name"] == "r2.png"


def test_write_note_rules(client, token):
    created = call(client, token, "write_note", path="01_Projects/Trip.md", content="# Trip\n- [ ] Book flights\n")
    assert created["created"] and not created["private"]
    assert "already exists" in call(client, token, "write_note", path="01_Projects/Trip.md", content="x")["error"]
    assert call(client, token, "write_note", path="01_Projects/Trip.md", content="# Trip v2", overwrite=True)["created"] is False
    call(client, token, "append_to_note", path="01_Projects/Trip.md", text="More")
    assert call(client, token, "read_note", path="01_Projects/Trip.md")["content"] == "# Trip v2\n\nMore\n"

    private = call(client, token, "write_note", path="Private/Ideas.md", content="secret")
    assert private["private"] is True
    assert "error" in call(client, token, "read_note", path="Private/Ideas.md")
    assert "error" in call(client, token, "write_note", path="../escape.md", content="x")
    call(client, token, "delete_note", path="01_Projects/Trip.md")
    assert "error" in call(client, token, "read_note", path="01_Projects/Trip.md")


def test_task_and_calendar_writes(client, token):
    task = call(client, token, "create_task", title="Write essay", due_date=TODAY, priority="high", subtasks=["outline"])
    call(client, token, "update_task", task_id=task["id"], estimated_minutes=90)
    sub = call(client, token, "add_subtask", task_id=task["id"], title="draft")
    call(client, token, "update_subtask", task_id=task["id"], subtask_id=sub["id"], is_completed=True)
    listed = next(t for t in call(client, token, "list_tasks") if t["id"] == task["id"])
    assert listed["estimated_minutes"] == 90 and [s["is_completed"] for s in listed["subtasks"]] == [0, 1]
    call(client, token, "update_task", task_id=task["id"], status="completed")
    assert all(t["id"] != task["id"] for t in call(client, token, "list_tasks"))
    call(client, token, "delete_task", task_id=task["id"])

    ev = call(client, token, "create_event", title="Gym", start_time=f"{TODAY} 07:00", end_time=f"{TODAY} 08:00",
              sync_to_google=False)
    call(client, token, "update_event", event_id=ev["id"], title="Gym (legs)")
    assert [e["title"] for e in call(client, token, "list_events", start_date=TODAY, end_date=TODAY)] == ["Gym (legs)"]
    gaps = call(client, token, "find_free_time", date=TODAY)["gaps"]
    assert gaps and all("Secret task" not in json.dumps(g) for g in gaps)
    call(client, token, "delete_event", event_id=ev["id"])
    assert call(client, token, "list_events", start_date=TODAY, end_date=TODAY) == []


def test_finance_health_learning_habit_writes(client, token):
    tx = call(client, token, "add_transaction", date=TODAY, amount=4.5, type="expense", category="food", merchant="Bakery")
    call(client, token, "update_transaction", transaction_id=tx["id"], amount=5.0)
    assert any(t["merchant"] == "Bakery" and t["amount"] == 5.0 for t in call(client, token, "list_transactions"))
    acct = call(client, token, "add_account", name="Visa", type="credit_card", starting_balance=-100)
    call(client, token, "update_account", account_id=acct["id"], name="Visa Card")
    assert "Invalid value" in call(client, token, "update_account", account_id=acct["id"], type="bogus")["error"]
    call(client, token, "delete_transaction", transaction_id=tx["id"])

    call(client, token, "log_vitals", date=TODAY, sleep_hours=7.5)
    call(client, token, "log_vitals", date=TODAY, water_ml=1500)
    today = next(v for v in call(client, token, "list_health_logs", kind="vitals") if v["date"] == TODAY)
    assert today["sleep_hours"] == 7.5 and today["water_ml"] == 1500  # second call kept the first value

    w = call(client, token, "log_workout", date=TODAY, activity_type="run", duration_minutes=30)
    call(client, token, "delete_health_entry", kind="fitness", entry_id=w["id"])
    call(client, token, "log_learning", date=TODAY, topic="Graphs", category="Computer Science", hours_spent=1.5)
    call(client, token, "log_habit", date=TODAY, habit_name="Read")
    assert call(client, token, "list_habits")[0]["habit_name"] == "Read"
    call(client, token, "delete_habit_log", date=TODAY, habit_name="Read")
    assert call(client, token, "list_habits") == []


def test_write_scopes_are_enforced(client):
    reader = mcp_server.create_token("reader", list(mcp_server.DOMAINS))
    assert "tasks:write" in call(client, reader, "create_task", title="x")["error"]
    assert "notes:write" in call(client, reader, "mark_note_private", path="01_Projects/Public.md")["error"]
    assert isinstance(call(client, reader, "list_tasks"), list)
