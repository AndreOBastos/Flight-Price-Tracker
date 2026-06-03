@echo off
REM Starts the Air Ticket Price Finder on Windows and opens the web UI.
REM Bootstraps Python and Node.js automatically (via winget) when missing.
REM Closing this console window will stop the server.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set PORT=47823
set PYTHON_CMD=
set NODE_OK=

echo === Air Ticket Price Finder ===
echo.

REM ----- Step 1: Ensure Python is installed and callable ---------------------

call :detect_python
if not defined PYTHON_CMD (
  echo [setup] Python not found on PATH.
  call :ensure_winget || goto :fatal_missing_python
  echo [setup] Installing Python 3.13 via winget. This may take a minute...
  winget install -e --id Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements
  if errorlevel 1 goto :fatal_missing_python
  call :refresh_path
  call :detect_python
  if not defined PYTHON_CMD goto :fatal_missing_python
)
echo [ok]    Using Python: %PYTHON_CMD%

REM ----- Step 2: Ensure Node.js is installed and callable --------------------

where node >nul 2>&1
if errorlevel 1 (
  echo [setup] Node.js not found on PATH.
  call :ensure_winget || goto :fatal_missing_node
  echo [setup] Installing Node.js LTS via winget. This may take a minute...
  winget install -e --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
  if errorlevel 1 goto :fatal_missing_node
  call :refresh_path
  where node >nul 2>&1
  if errorlevel 1 goto :fatal_missing_node
)
echo [ok]    Using Node.js:
node --version

REM ----- Step 3: Create venv + install Python deps (first run) ---------------

if not exist .venv (
  echo [setup] Creating Python virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create the Python venv.
    pause
    exit /b 1
  )
  call .venv\Scripts\activate.bat
  echo [setup] Installing backend dependencies...
  python -m pip install --upgrade pip --quiet
  pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo ERROR: Failed to install Python packages.
    pause
    exit /b 1
  )
  echo [setup] Installing Playwright Chromium browser...
  python -m playwright install chromium
  if errorlevel 1 (
    echo ERROR: Failed to install Playwright Chromium.
    pause
    exit /b 1
  )
) else (
  call .venv\Scripts\activate.bat
)

REM ----- Step 4: Build frontend (first run) ----------------------------------

if not exist frontend\dist (
  echo [setup] Installing frontend dependencies (this is a one-time step)...
  pushd frontend
  call npm install --silent
  if errorlevel 1 (
    popd
    echo ERROR: npm install failed.
    pause
    exit /b 1
  )
  echo [setup] Building frontend bundle...
  call npm run build
  if errorlevel 1 (
    popd
    echo ERROR: npm build failed.
    pause
    exit /b 1
  )
  popd
)

REM ----- Step 5: Launch ------------------------------------------------------

echo.
echo [start] Launching server on http://localhost:%PORT% ...
echo         Close this window to stop the server.
echo.

REM Open the default browser a few seconds after the server starts.
start "" /b cmd /c "timeout /t 4 /nobreak >nul && start "" http://localhost:%PORT%/"

uvicorn backend.main:app --host 127.0.0.1 --port %PORT%
goto :eof

REM ===========================================================================
REM Subroutines
REM ===========================================================================

:detect_python
REM Set PYTHON_CMD to whichever python launcher works (python or py).
REM Skips the Microsoft Store stub by checking that --version actually prints.
set PYTHON_CMD=
where python >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%V in ('python --version 2^>nul') do (
    echo %%V | findstr /b /c:"Python 3" >nul && set PYTHON_CMD=python
  )
)
if defined PYTHON_CMD goto :eof
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%V in ('py -3 --version 2^>nul') do (
    echo %%V | findstr /b /c:"Python 3" >nul && set PYTHON_CMD=py -3
  )
)
goto :eof

:ensure_winget
where winget >nul 2>&1
if errorlevel 1 (
  echo ERROR: winget is not available on this system, so I can't install
  echo        missing dependencies automatically. Please install them by hand:
  echo          - Python 3.11+   https://www.python.org/downloads/
  echo          - Node.js LTS    https://nodejs.org/
  echo        Then re-run start.bat.
  pause
  exit /b 1
)
goto :eof

:refresh_path
REM Re-read the User and Machine PATH from the registry so newly-installed
REM tools become available in THIS console session without a restart.
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul ^| find "REG_"') do set "_MACHINE_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul ^| find "REG_"') do set "_USER_PATH=%%B"
if defined _USER_PATH set "PATH=%_USER_PATH%;%PATH%"
if defined _MACHINE_PATH set "PATH=%_MACHINE_PATH%;%PATH%"
goto :eof

:fatal_missing_python
echo.
echo ERROR: Python is required but couldn't be installed automatically.
echo        Install Python 3.11 or newer from https://www.python.org/downloads/
echo        (be sure to tick "Add Python to PATH" in the installer),
echo        then re-run start.bat.
pause
exit /b 1

:fatal_missing_node
echo.
echo ERROR: Node.js is required but couldn't be installed automatically.
echo        Install Node.js LTS from https://nodejs.org/ and re-run start.bat.
pause
exit /b 1
