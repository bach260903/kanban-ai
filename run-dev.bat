@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ==========================================
echo   Kanban Dev Launcher (Backend + Frontend)
echo ==========================================
echo.

echo [1/4] Freeing port 8001 if occupied...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
  echo   - Killing PID %%p on 8001
  taskkill /PID %%p /F >nul 2>nul
)

echo [2/4] Freeing port 3000 if occupied...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
  echo   - Killing PID %%p on 3000
  taskkill /PID %%p /F >nul 2>nul
)

echo [3/4] Starting backend on http://127.0.0.1:8001 ...
start "Kanban Backend" cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001"

echo [4/4] Starting frontend on http://localhost:3000 ...
start "Kanban Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --port 3000"

echo.
echo Started:
echo - Backend : http://localhost:8001/docs
echo - Frontend: http://localhost:3000
echo.
echo Press any key to close this launcher window...
pause >nul

