#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "===================================================="
echo "  Starting SwasthAI Healthcare Platform..."
echo "===================================================="

# 1. Start FastAPI Backend
echo "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..."
(cd backend && ./venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

# 2. Start Frontend Server
echo "[2/2] Starting Frontend Server on http://localhost:5500..."
(cd frontend && python -m http.server 5500 --bind 127.0.0.1) &
FRONTEND_PID=$!

echo "===================================================="
echo "  Both servers are running concurrently!"
echo "  - Frontend:    http://localhost:5500"
echo "  - Backend API: http://127.0.0.1:8000"
echo "  - Swagger UI:  http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop both servers."
echo "===================================================="

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
