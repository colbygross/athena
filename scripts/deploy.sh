#!/bin/bash
# Production deploy for Athena on archer. Run by the CI "deploy" job after tests pass on main.
#
# Production is exactly one container (athena-prod) running the image built here from main.
# Code and the frontend bundle live only in that image; storage/ (database, tokens) and the
# vault are the only things mounted from the host. The job fails if the app isn't healthy.
set -euo pipefail

# Everything runs inside main() so bash has read the whole script before `git reset` can
# replace this file mid-run.
main() {
    local dir
    dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
    cd "$dir"

    echo "=== ATHENA PRODUCTION DEPLOY ==="
    echo "[1/4] Syncing to origin/main..."
    git fetch origin main
    git checkout -q -f main
    git reset --hard origin/main
    git log --oneline -1

    echo "[2/4] Checking database location..."
    # One-time move: the database used to live in backend/, inside the code tree.
    if [ -f backend/life_dashboard.db ] && [ ! -f storage/life_dashboard.db ]; then
        echo "Moving backend/life_dashboard.db to storage/..."
        docker compose stop athena || true
        mkdir -p storage
        for suffix in "" "-wal" "-shm"; do
            if [ -f "backend/life_dashboard.db$suffix" ]; then
                mv "backend/life_dashboard.db$suffix" "storage/life_dashboard.db$suffix"
            fi
        done
    fi

    echo "[3/4] Building image and starting athena-prod..."
    # --pull fetches the latest node/python base images so OS and runtime patches land each deploy.
    docker compose build --pull
    # The app runs as archer (uid 1000); make sure nothing in the data dirs is left root-owned
    # or unreadable (older containers ran as root and wrote 0600 files).
    docker compose run --rm --no-deps --user root --entrypoint sh athena -c \
        "chown -R 1000:1000 /app/obsidian_vault /app/storage && find /app/obsidian_vault -type f -perm 600 -exec chmod 644 {} +"
    # --remove-orphans also removes any container left in the 'athena' project that
    # docker-compose.yml doesn't define (e.g. the old dev stack).
    docker compose up -d --remove-orphans

    echo "[4/4] Waiting for Athena to respond..."
    for _ in $(seq 1 45); do
        if curl -fsS -o /dev/null http://127.0.0.1:8000/openapi.json \
            && curl -fsS -o /dev/null http://127.0.0.1:8000/; then
            docker image prune -f > /dev/null
            echo "=== ATHENA DEPLOYMENT SUCCESSFUL ==="
            return 0
        fi
        sleep 2
    done

    echo "Athena did not become healthy within 90s. Recent logs:" >&2
    docker compose logs --tail 80 athena >&2
    return 1
}

main "$@"
exit $?
