# Stage 1: Build frontend assets
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# The production bundle always calls its own origin (/api); never bake in another backend URL.
ENV VITE_API_URL=""
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies (poppler-utils needed for PDF text extraction via pdftotext)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application code
COPY backend/ ./backend/

# Copy built frontend assets for FastAPI static hosting
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Default directories for persistent data
RUN mkdir -p /app/obsidian_vault /app/storage

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    TZ=America/New_York \
    DB_PATH=/app/storage/life_dashboard.db \
    WORKSPACE_DIR=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/openapi.json > /dev/null || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
