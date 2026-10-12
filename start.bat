@echo off
title SwasthAI Application Launcher
echo ====================================================
echo   Starting SwasthAI Healthcare Platform...
echo ====================================================

REM Ensure we run from this script's directory
cd /d "%~dp0"

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "SwasthAI Backend (FastAPI)" cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo [2/2] Starting Frontend Server on http://localhost:5500 ...
start "SwasthAI Frontend" cmd /k "cd frontend && python -m http.server 5500 --bind 127.0.0.1"

echo ====================================================
echo   Both servers launched successfully!
echo   - Frontend:    http://localhost:5500
echo   - Backend API: http://127.0.0.1:8000
echo   - Swagger API: http://127.0.0.1:8000/docs
echo ====================================================
pause
