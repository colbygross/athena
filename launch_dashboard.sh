#!/bin/bash

# Get the absolute path to this script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo -e "\033[1;36m[Athena OS] Initializing Neural Link...\033[0m"

# Resolve Python environment
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python"
elif [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_BIN="$DIR/venv/bin/python"
else
    PYTHON_BIN="python3"
fi

# Start FastAPI backend
echo -e "\033[1;32m[Athena OS] Starting Backend Service on http://localhost:8000...\033[0m"
cd "$DIR"
$PYTHON_BIN "$DIR/backend/main.py" &
BACKEND_PID=$!

# Start Vite React frontend
echo -e "\033[1;32m[Athena OS] Starting Frontend Dev Server on http://localhost:5173...\033[0m"
cd "$DIR"/frontend
npm run dev &
FRONTEND_PID=$!

# Handle shutdown cleanly on Ctrl+C (SIGINT)
cleanup() {
    echo -e "\n\033[1;31m[Athena OS] Terminating services and severing link...\033[0m"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT

# Wait for both processes to complete
wait
