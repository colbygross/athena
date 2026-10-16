# Codebase Architecture & Service Layers

Athena OS is composed of a **FastAPI backend service** in Python and a **Vite + React frontend client** in JavaScript. The codebase also features bidirectional task/calendar synchronizers and background ingestion pipelines.

---

## 1. Backend REST API Endpoints

The backend is hosted in [backend/main.py](../backend/main.py). It exposes REST endpoints supporting JSON payloads:

### 1.1. Core System & Overview
*   `GET /api/overview` — Compiles the landing HUD metadata: current time, active Google and local ICS events, pending daily tasks, habit checklist completion percentages, and system status logs.
*   `POST /api/agent/run` — Manually triggers the local sync agent thread to process files in the Vault Inbox, reconcile tasks, and refresh summaries.

### 1.2. Financial Management
*   `GET /api/finances` — Returns accounts list, net worth history, transactions ledger, recurring bills, and budget metrics.
*   `POST /api/finances/transactions` — Logs a double-entry income/expense transaction.
*   `POST /api/finances/accounts` — Creates checking, savings, cash, or credit accounts.
*   `POST /api/finances/budgets` — Establishes monthly budget limits.
*   `POST /api/finances/recurring` — Configures subscription and automated bill cycles.
*   `POST /api/finances/student-loans` — Creates/edits student loans (balances, rates, types).

### 1.3. Health & Fitness Vitals
*   `GET /api/fitness` — Returns workout logs history and total activity statistics.
*   `POST /api/fitness` — Logs a new workout session (activity, duration, intensity, notes).
*   `GET /api/health` — Returns daily health vitals log history.
*   `POST /api/health` — Logs daily stats (weight, sleep, mood, BP, hydration, energy, stress) and automatically calculates a wellbeing score (0-100).

### 1.4. Learning & Career
*   `GET /api/learning` — Returns CS study categories, hours, and topics registry.
*   `POST /api/learning` — Logs completed learning concepts and sources.
*   `GET /api/career` — Returns applications (with timelines), open leads, and status counts.
*   `POST /api/career` — Logs a job application; repeats update the matching application (same URL, or company + role within 90 days).
*   `GET | PUT | DELETE /api/career/applications/{id}` — Read, edit (status changes go on the timeline), or delete an application.
*   `POST /api/career/applications/{id}/events` — Adds a timeline event (`interview`, `recruiter_contact`, `offer`, `note`, `status_change`).
*   `POST /api/career/leads`, `POST /api/career/leads/{id}/ignore`, `POST /api/career/leads/{id}/promote` — Add, dismiss, or promote a lead to an application.
*   Agents use the same operations through the MCP server at `/mcp`. See [mcp.md](mcp.md).

### 1.5. Tasks & Habit Checklists
*   `GET /api/tasks` — Returns all active tasks in the system.
*   `PUT /api/tasks/{task_id}/toggle` — Toggles task state between `pending` and `completed`.
*   `POST /api/habits` — Logs daily completion of habits.

### 1.6. Calendar Sync
*   `GET /api/calendar` — Retreives combined calendar schedules.
*   `POST /api/calendar` — Creates a local calendar event.

---

## 2. Frontend React Client Architecture

The frontend is a Vite React client located in [frontend/](../frontend). 

*   **Entry Mount**: [frontend/src/main.jsx](../frontend/src/main.jsx)
*   **Root Layout Component**: [frontend/src/App.jsx](../frontend/src/App.jsx)

### 2.1. State Management & Data Fetching
*   React hooks (`useState`, `useEffect`) manage tab rendering, toggle configurations, and form states.
*   The system uses an asynchronous function `fetchAllData()` to query the API routes concurrently:
    ```javascript
    const fetchAllData = async () => {
      const [overRes, finRes, fitRes, hlhRes, mealRes] = await Promise.all([
        fetch(`${API_BASE}/overview`).then(r => r.json()),
        fetch(`${API_BASE}/finances`).then(r => r.json()),
        // ...
      ]);
      setOverviewData(overRes);
      setFitnessData(fitRes);
      // ...
    };
    ```
*   Toggling checklist items or submitting log forms triggers an immediate callback to `fetchAllData()` to repaint views.

### 2.2. Persistent State in Local Storage
The client synchronizes configurations in the browser's `localStorage` to ensure they persist across session reloads:
*   `athena-theme`: Stores UI theme state (`dark` vs `light`).
*   `sidebar-collapsed`: Controls collapsed panel mode.
*   `athena-fitness-exercises`: Remembers checked items of the selected workout regimen day.

---

## 3. Bidirectional Sync Daemons

The synchronization layers run inside the daemon logic defined in [backend/agent.py](../backend/agent.py):

### 3.1. Bidirectional Tasks Synchronizer
This task coordinator reconciles the database task table state with checkboxes found in Obsidian Vault markdown files:
1.  **Scanning Phase**: Recursively walks the vault (skipping index and archives folders) searching for markdown checkmarks: `- [ ]` (pending) and `- [x]` (completed).
2.  **Parsing Phase**: Extracts due dates (`📅 YYYY-MM-DD`), priorities (`#high`, `#medium`, `#low`), and importance (`#major`, `#minor`) from the task string.
3.  **Database Reconciliation**:
    *   Adds new markdown checklists as database tasks.
    *   Toggles database row status to `completed` if checked in markdown.
    *   Rewrites markdown lines in notes to `- [x]` if marked complete in the database.
4.  **Master Tasks Compiler**: Compiles all unresolved tasks and tasks finished in the last 24 hours into [obsidian_vault/tasks.md](../obsidian_vault/tasks.md) grouped by category.

### 3.2. Google Calendar Sync
*   **Auth**: uses the OAuth token at `storage/token.json` (or `backend/token.json`). Create it by running `backend/setup_google_calendar.py`; the server never starts an OAuth flow itself. Without a usable token, sync reports *not connected* (HTTP 400). Refreshed tokens are written back to disk, and the API client is cached per process, so restart the server after re-authorizing.
*   **Time zones**: Athena stores naive local wall-clock times. Pushes send RFC3339 with the local offset plus the IANA zone (`ATHENA_TIMEZONE`, falling back to the system zone via `tzlocal`). Pulls convert Google offsets to local time.
*   **All-day events**: stored from `00:00:00` on the start date to `23:59:59` on the last day (Google's `end.date` is exclusive).
*   **Pull window**: follows `nextPageToken` over a rolling viewport (-30 to +60 days) with `showDeleted=True`; cancelled items are dropped. Google-sourced rows inside the window that Google no longer returns are deleted, and tasks linked to them are detached. Nothing is deleted when the fetch fails.
*   **Conflicts**: last write wins from Google. A local edit to a synced event is overwritten on the next pull.
*   **Pending pushes**: an event created while Google rejects the push is saved with `google_pending = 1` and pushed at the start of the next sync. Edits to Google-sourced events are pushed first and saved locally only if Google accepts them.
*   **Endpoint**: `POST /api/calendar/sync-google` returns `added`, `updated`, `deleted` and `pushed` counts, or 400 (not connected) / 502 (Google API error).

### 3.3. ICS Calendar Sync
*   Synchronizes local calendar entries with the text-file schedule [obsidian_vault/calendar.ics](../obsidian_vault/calendar.ics).
*   Enables external calendar clients (like Apple Calendar or Google) to subscribe to Athena.

---

## 4. Background Cron Pipelines

The system is automated by four Python scripts executed periodically by system service managers:

1.  **Ingestion Scanner ([backend/run_inbox.py](../backend/run_inbox.py))**:
    *   Runs when files are placed in Vault's `Inbox/`.
    *   Uses OCR / text-extraction tools and prompts a local LLM (e.g. Qwen/Phi-4 via Ollama) to extract receipt amounts, merchants, medical diagnostics, or CS concepts.
    *   Renames files to `YYYY-MM-DD_name.ext`, saves them under `storage/`, inserts database logs, and writes companion vault notes.
2.  **Nightly Pipeline ([backend/run_nightly.py](../backend/run_nightly.py))**:
    *   Runs nightly at 23:59 as a unified 3-step pipeline:
        1. **Daily Archive**: Archives today's events, completed tasks, financial transactions, and most recent vitals log to `obsidian_vault/04_Archives/Daily_Summary_YYYY-MM-DD.md`, and cleans up today's daily brief.
        2. **Garbage Collection & Task Reset**: Permanently purges completed one-off tasks from SQLite, resets recurring tasks (daily, weekly, monthly) to pending, and synchronizes `obsidian_vault/tasks.md`.
        3. **Tomorrow's Daily Brief**: Generates `obsidian_vault/Daily_Briefs/Daily_Brief_YYYY-MM-DD.md` for tomorrow with schedule, pending/overdue tasks, and the scheduled workout routine.
3.  **Rolling Summaries Builder ([backend/run_summaries.py](../backend/run_summaries.py))**:
    *   Standalone utility to regenerate vault index files under `obsidian_vault/Summaries/` (`Financial_Summary.md`, `Health_Fitness_Summary.md`, and `Learning_Career_Summary.md`) on demand or via specialized local LLM runs.

---

## 5. Environment Configuration & Container Service Layers

Athena runs as a single production container on archer, deployed by CI from `main` (see [deployment.md](deployment.md)).

### 5.1. Runtime Environment Variables
* `DB_PATH`: Location of the SQLite database. Defaults to `$STORAGE_DIR/life_dashboard.db`.
* `WORKSPACE_DIR`: Base directory for storage and vault paths.
* `VAULT_DIR`: Custom path to the Obsidian Vault (defaults to `$WORKSPACE_DIR/obsidian_vault`).
* `STORAGE_DIR`: Custom path to flat storage assets (defaults to `$WORKSPACE_DIR/storage`).
* `VITE_API_URL`: (Frontend, local dev only) Explicit API URL. Production builds leave it empty.

### 5.2. Service Architecture
* **Production Service ([Dockerfile](../Dockerfile) & `docker-compose.yml`)**:
  * `athena-prod` (Port 8000): Unified container serving both the API and the compiled frontend from the image. Only `storage/` and the vault are mounted.
  * Managed via Dockge .
