#!/usr/bin/env bash
# Starts the Air Ticket Price Finder on Linux and opens the web UI.
# Closing the terminal window will stop the server.

set -e
cd "$(dirname "$0")"

PORT=47823

# Create venv on first run.
if [ ! -d .venv ]; then
  echo "[setup] Creating Python venv..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r backend/requirements.txt
  python3 -m playwright install chromium
  # Install system deps for Chromium on Debian/Ubuntu (best effort).
  python3 -m playwright install-deps chromium 2>/dev/null || true
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Build frontend on first run.
if [ ! -d frontend/dist ]; then
  echo "[setup] Installing frontend deps..."
  (cd frontend && npm install --silent && npm run build)
fi

# Ensure the server dies when this shell exits (terminal close → SIGHUP).
cleanup() {
  echo "[stop] Shutting down server..."
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM HUP

echo "[start] Launching server on http://localhost:$PORT ..."
uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!

# Wait for the server to accept connections before opening the browser.
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/api/currencies" >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

# Pick whichever browser-opener is available on Linux.
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:$PORT/" >/dev/null 2>&1 || true
elif command -v gnome-open >/dev/null 2>&1; then
  gnome-open "http://localhost:$PORT/" >/dev/null 2>&1 || true
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "http://localhost:$PORT/" >/dev/null 2>&1 || true
else
  echo "[info] No browser-opener found. Open http://localhost:$PORT/ manually."
fi

echo "[ready] Close this window to stop the server."
wait "$SERVER_PID"
