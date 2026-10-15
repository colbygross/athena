"""
Google Calendar sync tests. The Google API is always a MagicMock; nothing here calls the real service.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

import agent
import database


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "calendar_test.db"))
    database.init_db()


@pytest.fixture
def ny_zone(monkeypatch):
    monkeypatch.setenv("ATHENA_TIMEZONE", "America/New_York")


@pytest.fixture
def svc(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(agent, "get_google_calendar_service", lambda: service)
    return service


def _rows(sql, args=()):
    conn = database.create_new_connection()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _insert_event(uid, start, end, source="google", title="Event"):
    conn = database.create_new_connection()
    conn.execute(
        "INSERT INTO calendar_events (title, description, start_time, end_time, source, event_uid, tags, color) "
        "VALUES (?, '', ?, ?, ?, ?, '[]', '#4facfe')",
        (title, start, end, source, uid),
    )
    conn.commit()
    conn.close()


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# --- Item 1: timezone conversion ---

def test_push_sends_local_wall_time_with_offset_and_iana_zone(ny_zone, svc):
    svc.events.return_value.insert.return_value.execute.return_value = {"id": "g1"}

    gid = agent.push_event_to_google("Dentist", "", "2026-10-15 09:00:00", "2026-10-15 10:30")

    assert gid == "g1"
    body = svc.events.return_value.insert.call_args.kwargs["body"]
    assert body["start"] == {"dateTime": "2026-10-15T09:00:00-04:00", "timeZone": "America/New_York"}
    assert body["end"] == {"dateTime": "2026-10-15T10:30:00-04:00", "timeZone": "America/New_York"}


def test_push_uses_standard_offset_in_winter(ny_zone, svc):
    svc.events.return_value.insert.return_value.execute.return_value = {"id": "g2"}

    agent.push_event_to_google("Winter", "", "2026-01-15 09:00", "2026-01-15 10:00")

    body = svc.events.return_value.insert.call_args.kwargs["body"]
    assert body["start"]["dateTime"] == "2026-01-15T09:00:00-05:00"


def test_update_uses_same_conversion(ny_zone, svc):
    agent.update_event_in_google("g1", "Moved", "", "2026-10-15 13:00:00", "2026-10-15 14:00:00")

    body = svc.events.return_value.patch.call_args.kwargs["body"]
    assert body["start"]["dateTime"] == "2026-10-15T13:00:00-04:00"


def test_pull_converts_google_offsets_to_local_time(tmp_db, ny_zone, svc, monkeypatch):
    # Window is now-relative; these fixed-date items are upserted regardless of the window.
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "utc1", "summary": "UTC event",
         "start": {"dateTime": "2026-10-15T13:00:00Z"}, "end": {"dateTime": "2026-10-15T14:00:00Z"}},
        {"id": "off1", "summary": "Offset event",
         "start": {"dateTime": "2026-10-15T09:00:00-04:00"}, "end": {"dateTime": "2026-10-15T10:00:00-04:00"}},
    ]}

    agent.sync_google_calendar_to_db()

    rows = {r["event_uid"]: r for r in _rows("SELECT * FROM calendar_events WHERE source = 'google'")}
    assert rows["utc1"]["start_time"] == "2026-10-15 09:00:00"
    assert rows["utc1"]["end_time"] == "2026-10-15 10:00:00"
    assert rows["off1"]["start_time"] == "2026-10-15 09:00:00"
    assert rows["off1"]["end_time"] == "2026-10-15 10:00:00"


def test_push_then_pull_round_trips_wall_time(ny_zone, svc):
    body_store = {}

    def fake_insert(calendarId, body):
        body_store.update(body)
        return MagicMock(execute=MagicMock(return_value={"id": "rt1"}))

    svc.events.return_value.insert.side_effect = fake_insert
    agent.push_event_to_google("RT", "", "2026-07-04 18:45:00", "2026-07-04 19:45:00")

    # Google echoes the stored dateTime back; pulling it must give the original local wall time.
    echoed = body_store["start"]["dateTime"]
    assert agent.google_time_to_athena(echoed) == "2026-07-04 18:45:00"


# --- Item 2: all-day events ---

def test_all_day_event_end_date_is_exclusive(tmp_db, ny_zone, svc):
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "trip1", "summary": "Trip",
         "start": {"date": "2026-10-15"}, "end": {"date": "2026-10-17"}},
    ]}

    agent.sync_google_calendar_to_db()

    row = _rows("SELECT start_time, end_time FROM calendar_events WHERE event_uid = 'trip1'")[0]
    assert row["start_time"] == "2026-10-15 00:00:00"
    assert row["end_time"] == "2026-10-16 23:59:59"


def test_single_day_all_day_event_stays_on_its_day(tmp_db, ny_zone, svc):
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "bday1", "summary": "Birthday",
         "start": {"date": "2026-10-15"}, "end": {"date": "2026-10-16"}},
    ]}

    agent.sync_google_calendar_to_db()

    row = _rows("SELECT start_time, end_time FROM calendar_events WHERE event_uid = 'bday1'")[0]
    assert row["start_time"] == "2026-10-15 00:00:00"
    assert row["end_time"] == "2026-10-15 23:59:59"


# --- Item 3: pagination ---

def test_sync_follows_next_page_token(tmp_db, ny_zone, svc):
    page1 = {"items": [{"id": "p1", "summary": "First",
                        "start": {"dateTime": "2026-10-15T09:00:00-04:00"},
                        "end": {"dateTime": "2026-10-15T10:00:00-04:00"}}],
             "nextPageToken": "tok2"}
    page2 = {"items": [{"id": "p2", "summary": "Second",
                        "start": {"dateTime": "2026-10-16T09:00:00-04:00"},
                        "end": {"dateTime": "2026-10-16T10:00:00-04:00"}}]}
    svc.events.return_value.list.return_value.execute.side_effect = [page1, page2]

    agent.sync_google_calendar_to_db()

    uids = {r["event_uid"] for r in _rows("SELECT event_uid FROM calendar_events")}
    assert {"p1", "p2"} <= uids
    calls = svc.events.return_value.list.call_args_list
    assert len(calls) == 2
    assert "pageToken" not in calls[0].kwargs
    assert calls[1].kwargs["pageToken"] == "tok2"
    assert calls[0].kwargs["showDeleted"] is True


# --- Item 4: deletions and cancellations ---

def test_sync_removes_google_rows_missing_from_fetch_and_detaches_tasks(tmp_db, ny_zone, svc):
    now = datetime.now()
    in_window = _fmt((now + timedelta(days=5)).replace(hour=9, minute=0, second=0, microsecond=0))
    in_window_end = _fmt((now + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0))
    past_in_window = _fmt((now - timedelta(days=10)).replace(hour=9, minute=0, second=0, microsecond=0))
    past_in_window_end = _fmt((now - timedelta(days=10)).replace(hour=10, minute=0, second=0, microsecond=0))
    outside = _fmt((now + timedelta(days=90)).replace(hour=9, minute=0, second=0, microsecond=0))
    outside_end = _fmt((now + timedelta(days=90)).replace(hour=10, minute=0, second=0, microsecond=0))

    _insert_event("kept1", in_window, in_window_end)
    _insert_event("deleted1", past_in_window, past_in_window_end)
    _insert_event("cancelled1", in_window, in_window_end)
    _insert_event("outside1", outside, outside_end)
    _insert_event("local1", in_window, in_window_end, source="local_ics")

    conn = database.create_new_connection()
    deleted_id = conn.execute("SELECT id FROM calendar_events WHERE event_uid = 'deleted1'").fetchone()["id"]
    conn.execute("INSERT INTO tasks (title, event_id) VALUES ('Prep for deleted meeting', ?)", (deleted_id,))
    conn.commit()
    conn.close()

    kept_day = (now + timedelta(days=5)).date().isoformat()
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "kept1", "summary": "Kept", "start": {"date": kept_day},
         "end": {"date": (now + timedelta(days=6)).date().isoformat()}},
        {"id": "cancelled1", "status": "cancelled"},
    ]}

    agent.sync_google_calendar_to_db()

    uids = {r["event_uid"] for r in _rows("SELECT event_uid FROM calendar_events")}
    assert uids == {"kept1", "outside1", "local1"}
    task = _rows("SELECT event_id FROM tasks WHERE title = 'Prep for deleted meeting'")[0]
    assert task["event_id"] is None


def test_sync_does_not_delete_anything_when_fetch_fails(tmp_db, ny_zone, svc):
    now = datetime.now()
    start = _fmt((now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0))
    end = _fmt((now + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0))
    _insert_event("survivor1", start, end)
    svc.events.return_value.list.return_value.execute.side_effect = RuntimeError("Google is down")

    with pytest.raises(agent.GoogleCalendarAPIError):
        agent.sync_google_calendar_to_db()

    uids = {r["event_uid"] for r in _rows("SELECT event_uid FROM calendar_events")}
    assert uids == {"survivor1"}


def test_sync_does_not_delete_when_not_connected(tmp_db, ny_zone, monkeypatch):
    now = datetime.now()
    start = _fmt((now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0))
    _insert_event("survivor2", start, start)
    monkeypatch.setattr(agent, "get_google_calendar_service", lambda: None)

    with pytest.raises(agent.GoogleCalendarNotConnected):
        agent.sync_google_calendar_to_db()

    uids = {r["event_uid"] for r in _rows("SELECT event_uid FROM calendar_events")}
    assert uids == {"survivor2"}


# --- Item 5: server-side auth (no interactive OAuth, cached client, refreshed token written back) ---

@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(agent, "BASE_DIR", str(tmp_path / "base"))
    monkeypatch.setattr(agent, "_google_service", None)
    return tmp_path


def test_missing_token_returns_none_and_never_starts_oauth(storage, monkeypatch):
    (storage / "credentials.json").write_text("{}")  # present, so the old code would have started a browser flow
    flow_cls = MagicMock()
    monkeypatch.setattr(agent, "InstalledAppFlow", flow_cls)

    assert agent.get_google_calendar_service() is None

    flow_cls.from_client_secrets_file.assert_not_called()
    flow_cls.from_client_secrets_file.return_value.run_local_server.assert_not_called()


def test_expired_token_is_refreshed_and_written_back(storage, monkeypatch):
    token_path = storage / "token.json"
    token_path.write_text('{"token": "stale"}')
    creds = MagicMock(valid=False, expired=True, refresh_token="refresh-me")
    creds.to_json.return_value = '{"token": "fresh"}'
    monkeypatch.setattr(agent.Credentials, "from_authorized_user_file", MagicMock(return_value=creds))
    build = MagicMock(return_value="SERVICE")
    monkeypatch.setattr(agent, "build", build)

    assert agent.get_google_calendar_service() == "SERVICE"

    creds.refresh.assert_called_once()
    assert token_path.read_text() == '{"token": "fresh"}'


def test_failed_refresh_returns_none(storage, monkeypatch):
    (storage / "token.json").write_text("{}")
    creds = MagicMock(valid=False, expired=True, refresh_token="r")
    creds.refresh.side_effect = Exception("revoked")
    monkeypatch.setattr(agent.Credentials, "from_authorized_user_file", MagicMock(return_value=creds))
    build = MagicMock()
    monkeypatch.setattr(agent, "build", build)

    assert agent.get_google_calendar_service() is None
    build.assert_not_called()


def test_service_is_built_once_and_cached(storage, monkeypatch):
    (storage / "token.json").write_text("{}")
    creds = MagicMock(valid=True)
    monkeypatch.setattr(agent.Credentials, "from_authorized_user_file", MagicMock(return_value=creds))
    build = MagicMock(return_value="SERVICE")
    monkeypatch.setattr(agent, "build", build)

    first = agent.get_google_calendar_service()
    second = agent.get_google_calendar_service()

    assert first == second == "SERVICE"
    assert build.call_count == 1


# --- Item 6: typed failures and sync result ---

def test_sync_raises_not_connected_when_no_service(tmp_db, monkeypatch):
    monkeypatch.setattr(agent, "get_google_calendar_service", lambda: None)
    with pytest.raises(agent.GoogleCalendarNotConnected):
        agent.sync_google_calendar_to_db()


def test_sync_raises_api_error_on_fetch_failure(tmp_db, svc):
    svc.events.return_value.list.return_value.execute.side_effect = RuntimeError("500 from Google")
    with pytest.raises(agent.GoogleCalendarAPIError):
        agent.sync_google_calendar_to_db()


def test_sync_returns_counts(tmp_db, ny_zone, svc):
    _insert_event("upd1", "2026-10-15 08:00:00", "2026-10-15 08:30:00")
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "upd1", "summary": "Updated", "start": {"dateTime": "2026-10-15T09:00:00-04:00"},
         "end": {"dateTime": "2026-10-15T10:00:00-04:00"}},
        {"id": "new1", "summary": "New", "start": {"dateTime": "2026-10-15T11:00:00-04:00"},
         "end": {"dateTime": "2026-10-15T12:00:00-04:00"}},
    ]}

    result = agent.sync_google_calendar_to_db()

    assert result == {"connected": True, "added": 1, "updated": 1, "deleted": 0, "error": None}


@pytest.fixture
def api_client(tmp_db):
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_sync_endpoint_reports_not_connected_as_400(api_client, monkeypatch):
    monkeypatch.setattr(agent, "get_google_calendar_service", lambda: None)
    res = api_client.post("/api/calendar/sync-google")
    assert res.status_code == 400
    assert "not connected" in res.json()["detail"].lower()


def test_sync_endpoint_reports_api_error_as_502(api_client, svc):
    svc.events.return_value.list.return_value.execute.side_effect = RuntimeError("quota exceeded")
    res = api_client.post("/api/calendar/sync-google")
    assert res.status_code == 502
    assert "quota exceeded" in res.json()["detail"]


def test_sync_endpoint_returns_counts_on_success(api_client, ny_zone, svc):
    svc.events.return_value.list.return_value.execute.return_value = {"items": [
        {"id": "ep1", "summary": "Endpoint", "start": {"dateTime": "2026-10-15T09:00:00-04:00"},
         "end": {"dateTime": "2026-10-15T10:00:00-04:00"}},
    ]}
    res = api_client.post("/api/calendar/sync-google")
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "success"
    assert (body["added"], body["updated"], body["deleted"]) == (1, 0, 0)
