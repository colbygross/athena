# Deployment & Containerization Architecture

ATHENA is engineered for dual-environment containerization: **Development / Staging** with hot reloading and **Production** with optimized static compilation.

---

## 1. Quick Reference

| Feature | Staging / Dev (`docker-compose.dev.yml`) | Production (`docker-compose.yml`) |
| :--- | :--- | :--- |
| **Purpose** | Rapid feature development & iteration | High-efficiency 24/7 background telemetry |
| **Ports** | `8001` (API), `5174` (Frontend UI) | `8000` (Unified UI + API) |
| **Database** | `backend/life_dashboard_staging.db` | `backend/life_dashboard.db` (Persistent) |
| **Code Changes** | **Instant hot-reload** (Uvicorn reload + Vite HMR) | Pre-compiled static assets in image |
| **Rebuild Needed?** | **Never** during coding | Only when updating dependencies/releases |

---

## 2. Staging / Development Environment (Zero-Rebuild Workflow)

Standard Docker setups copy code at build time (`COPY . /app`), necessitating slow container rebuilds on every code change. ATHENA eliminates this overhead using a zero-rebuild architecture:

1. **Live Host Bind-Mounts**:
   * `./backend` is mounted directly into `/app/backend`.
   * `./frontend` is mounted directly into `/app/frontend`.
2. **Backend Reloader**:
   * Uvicorn runs with `--reload --reload-dir backend` using `WatchFiles`. Any Python file edit restarts the server in under **500 ms**.
3. **Frontend Vite HMR**:
   * The container exposes Vite's development server. Edits in `frontend/src/` are hot-swapped into the browser session via WebSockets in **~50 ms** without refreshing the page.

### Launch Commands
```bash
# Start development environment
docker compose -f docker-compose.dev.yml up -d

# Inspect live logs
docker logs -f athena-backend-dev
docker logs -f athena-frontend-dev

# Tear down development environment
docker compose -f docker-compose.dev.yml down
```

---

## 3. Production Environment

### Multi-Stage Dockerfile
The production container utilizes an efficient multi-stage build:
* **Stage 1 (`frontend-builder`)**: Compiles the React + Vite single-page application into minified static assets (`dist/`).
* **Stage 2 (`python:3.12-slim`)**: Installs system tools (`poppler-utils` for OCR/PDF extraction), installs Python wheels, copies compiled static assets, and hosts both the API and client from FastAPI on port `8000`.

### Launch Commands
```bash
# Build and run production stack
docker compose up -d

# Check production health
curl -f http://localhost:8000/api/vitals/stats
```

### Persistent Data Volumes
Production safely mounts host directories to guarantee state persistence across container restarts:
* `backend/life_dashboard.db` (SQLite database with WAL mode enabled)
* `obsidian_vault/` (Notes, tasks, calendar ICS, daily briefs)
* `storage/` (Processed PDFs, receipts, document archives)

---

## 4. Secure Remote Access (Tailscale & Reverse Proxies)

For encrypted remote and mobile access across devices without opening public router ports:

### Tailscale Integration
Run ATHENA behind Tailscale on your host machine:
* **Local Web Interface**: `http://<tailscale-ip>:8000`
* **Tailscale Serve (Automatic HTTPS)**:
  ```bash
  sudo tailscale serve --bg 8000
  ```
  Provides valid public-trusted TLS certificates directly to `https://<node-name>.ts.net`.

### Reverse Proxy Configuration (Nginx / Caddy)
When hosting behind Nginx Proxy Manager, Traefik, or Caddy:
* **Forward Host**: `127.0.0.1`
* **Forward Port**: `8000`
* **WebSockets**: Enable support for real-time frontend telemetry updates.
