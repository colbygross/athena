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
*   `GET /api/career` — Returns job applications history and application progress states.
*   `POST /api/career` — Logs a new job application (company, role, status, URL).

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
*   Checks for `token.json` and `credentials.json` credentials in `backend/`.
*   Connects to Google Calendar API via OAuth2, fetching event items within a rolling viewport (-30 to +60 days).
*   Merges Google events with database rows marked with `source = 'google'`.

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
2.  **Daily Brief Generator ([backend/run_daily_brief.py](../backend/run_daily_brief.py))**:
    *   Runs daily at 05:00.
    *   Calculates the active workout regimen day index: `cycle_day = (today_dt - anchor_date).days % 4`.
    *   Injects schedules, outstanding tasks, habits, and today's workout checkbox list into `obsidian_vault/Daily_Briefs/Daily_Brief_YYYY-MM-DD.md`.
3.  **Nightly Retrospective ([backend/run_nightly.py](../backend/run_nightly.py))**:
    *   Runs daily at 23:59.
    *   Summarizes completed tasks, habits completed, nutrition macros, and biometrics.
    *   Creates a retrospective file at `obsidian_vault/04_Archives/Daily_Summary_YYYY-MM-DD.md` and deletes the active morning brief.
4.  **Rolling Summaries Builder ([backend/run_summaries.py](../backend/run_summaries.py))**:
    *   Summarizes logs from the past month to regenerate the main vault indices under `obsidian_vault/Summaries/` (`Financial_Summary.md`, `Health_Fitness_Summary.md`, and `Learning_Career_Summary.md`).

---

## 5. Environment Configuration & Container Service Layers

Athena supports decoupled environment routing allowing live hot-reloading in staging while maintaining a persistent production stack.

### 5.1. Runtime Environment Variables
The application dynamically adapts to its execution environment via:
* `DB_PATH`: Location of the SQLite database. Defaults to `backend/life_dashboard.db` in production and `backend/life_dashboard_staging.db` in staging.
* `WORKSPACE_DIR`: Base directory for storage and vault paths.
* `VAULT_DIR`: Custom path to the Obsidian Vault (defaults to `$WORKSPACE_DIR/obsidian_vault`).
* `STORAGE_DIR`: Custom path to flat storage assets (defaults to `$WORKSPACE_DIR/storage`).
* `VITE_API_URL`: (Frontend) Explicit override for API endpoint URL.

### 5.2. Service Architecture
* **Staging Service ([docker-compose.dev.yml](../docker-compose.dev.yml))**:
  * `athena-backend-dev` (Port 8001): Runs Uvicorn with `--reload` against bind-mounted code.
  * `athena-frontend-dev` (Port 5174): Runs Vite dev server with WebSocket HMR.
  * Requires zero container rebuilds on code modifications.
* **Production Service ([Dockerfile](../Dockerfile) & `docker-compose.yml`)**:
  * `athena-prod` (Port 8000): Unified container serving both API and compiled `frontend/dist` static assets.
  * Managed via Dockge .
