# Deployment & Containerization Architecture

Athena runs as **one production container** (`athena-prod`, port `8000`) on archer, deployed only through GitHub: push or merge to `main` → CI runs the tests and frontend build → the self-hosted runner on archer runs [`scripts/deploy.sh`](../scripts/deploy.sh).

There is no staging or dev stack on archer. Develop locally (see the README) and ship through a PR.

---

## 1. How a deploy works

1. The CI `deploy` job syncs `/home/archer/ATHENA` to `origin/main`, then runs `scripts/deploy.sh`.
2. `deploy.sh` runs `docker compose up -d --build --remove-orphans`. This rebuilds the image, so dependency changes are always installed, and it removes any stray container in the `athena` compose project.
3. It waits for `/openapi.json` and `/` to answer. If they don't within 90s, it prints the logs and **fails the job**.

What lives where:

| Thing | Location | Notes |
| :--- | :--- | :--- |
| Code + frontend bundle | Inside the image only | Never bind-mounted, so code and installed packages always match |
| Database | `storage/life_dashboard.db` (`/app/storage` in the container) | The only Athena database |
| Google tokens, MCP data, backups | `storage/` | Persistent |
| Obsidian vault | `obsidian_vault/` | Persistent |
| Nightly pipeline | archer crontab: `docker exec athena-prod python3 /app/backend/run_nightly.py` at 23:59 | |

The production bundle is built with an empty `VITE_API_URL`, so the UI always calls its own origin (`/api`).

---

## 2. Production Environment

### Multi-Stage Dockerfile
The production container utilizes an efficient multi-stage build:
* **Stage 1 (`frontend-builder`)**: Compiles the React + Vite single-page application into minified static assets (`dist/`).
* **Stage 2 (`python:3.12-slim`)**: Installs system tools (`poppler-utils` for OCR/PDF extraction), installs Python wheels, copies compiled static assets, and hosts both the API and client from FastAPI on port `8000`.

### Launch Commands
```bash
# Build and run production stack
docker compose up -d

# Check production health
curl -f http://localhost:8000/openapi.json
```

### Persistent Data Volumes
Production safely mounts host directories to guarantee state persistence across container restarts:
* `storage/life_dashboard.db` (SQLite database with WAL mode enabled)
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
