# Stage 1: Build frontend assets
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
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
    DB_PATH=/app/backend/life_dashboard.db \
    WORKSPACE_DIR=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
