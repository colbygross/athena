# Athena OS: Frontend Dashboard Client

The Athena OS dashboard is a React single-page application bundled with **Vite** and styled with **Tailwind CSS**. It connects to the FastAPI backend to render telemetry, charts, financial ledgers, vitals logs, and task checklists.

---

## 1. Development & Staging Execution

### Inside Docker (Recommended Workflow)
When running via the staging environment (`docker-compose.dev.yml`), Vite is hosted inside `athena-frontend-dev` with live bind-mounts:
* **URL**: `http://localhost:5174` (or `http://<your-host-ip>:5174`)
* **API Target**: Automatically points to the staging backend API on port `8001`.
* **Hot Module Replacement (HMR)**: Edits inside `src/` are hot-swapped into the active browser session in milliseconds without full page reloads or container rebuilds.

### Standalone Local Execution (Without Docker)
```bash
cd frontend
npm install
npm run dev
```
* Runs on `http://localhost:5173` and connects to `http://localhost:8000/api`.

---

## 2. Dynamic API Resolution

The frontend dynamically detects its runtime environment via `API_BASE` in `src/App.jsx`:
1. **Staging Container (Port 5174)**: Routes API requests to `http://<host>:8001/api`.
2. **Local Dev (Port 5173)**: Routes API requests to `http://<host>:8000/api`.
3. **Production Container (Port 8000)**: Uses relative path `${window.location.origin}/api` directly served by FastAPI.
4. **Environment Override**: Respects `import.meta.env.VITE_API_URL` when provided.

---

## 3. Production Build

To compile static assets for production:
```bash
npm run build
```
This outputs minified assets to `dist/`, which is copied into the multi-stage `Dockerfile` and statically hosted by FastAPI under `/` and `/assets`.
