@echo off
setlocal enabledelayedexpansion
set APP_DIR=%~dp0
cd /d %APP_DIR%

if not exist .venv (
  echo [INFO] Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\Activate.bat

python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

set PORT=9988

echo [INFO] Starting server on http://localhost:%PORT%
python -m uvicorn app.main:app --reload --port %PORT%

endlocal
