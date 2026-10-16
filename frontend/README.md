# Athena OS: Frontend Dashboard Client

The Athena OS dashboard is a React single-page application bundled with **Vite** and styled with **Tailwind CSS**. It connects to the FastAPI backend to render telemetry, charts, financial ledgers, vitals logs, and task checklists.

---

## 1. Development & Staging Execution

### Standalone Local Execution (Without Docker)
```bash
cd frontend
npm install
npm run dev
```
* Runs on `http://localhost:5173` and connects to `http://localhost:8000/api`.

---

## 2. Dynamic API Resolution

`API_BASE` lives in `src/api.js`:
1. **Local Dev (Port 5173)**: Routes API requests to `http://<host>:8000/api`.
2. **Production Container (Port 8000)**: Uses `${window.location.origin}/api`, served by FastAPI. The production image builds with an empty `VITE_API_URL`.
3. **Environment Override**: Respects `import.meta.env.VITE_API_URL` when provided (local dev only).

---

## 3. Production Build

To compile static assets for production:
```bash
npm run build
```
This outputs minified assets to `dist/`, which is copied into the multi-stage `Dockerfile` and statically hosted by FastAPI under `/` and `/assets`.
