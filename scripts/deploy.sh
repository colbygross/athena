#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== ATHENA PRODUCTION DEPLOY ==="
echo "[1/3] Pulling latest changes from origin/main..."
git pull origin main

echo "[2/3] Building frontend production bundle..."
if docker ps --format '{{.Names}}' | grep -q '^athena-frontend-dev$'; then
    docker exec athena-frontend-dev npm run build
else
    (cd frontend && npm run build) || docker compose run --rm athena-frontend-dev npm run build
fi

echo "[3/3] Restarting Athena production container..."
docker compose restart athena

echo "=== ATHENA DEPLOYMENT SUCCESSFUL ==="
