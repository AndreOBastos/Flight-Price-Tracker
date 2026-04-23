@echo off
REM Starts the Air Ticket Price Finder on Windows and opens the web UI.
REM Closing this console window will stop the server.

setlocal
cd /d "%~dp0"

set PORT=47823

REM Create venv on first run.
if not exist .venv (
  echo [setup] Creating Python venv...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -q -r backend\requirements.txt
  python -m playwright install chromium
) else (
  call .venv\Scripts\activate.bat
)

REM Build frontend on first run.
if not exist frontend\dist (
  echo [setup] Installing frontend deps...
  pushd frontend
  call npm install --silent
  call npm run build
  popd
)

echo [start] Launching server on http://localhost:%PORT% ...

REM Start uvicorn in this console window so Ctrl+C or closing the window
REM terminates the server. Open the browser after a short delay.
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start "" http://localhost:%PORT%/"

uvicorn backend.main:app --host 127.0.0.1 --port %PORT%
