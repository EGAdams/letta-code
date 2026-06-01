#!/usr/bin/env bash
#
# Start the dashboard HTTP server.
# Serves dashboard.html (and stub /api endpoints) on http://localhost:8765/
#
# Usage:
#   ./start.sh           # start in the foreground
#   PORT=9000 ./start.sh # start on a different port (passed through to server.py via env)
#
set -euo pipefail

# Resolve the directory this script lives in, so it works from any cwd.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8765}"

# Pick a Python interpreter.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Error: python3 (or python) is not installed." >&2
  exit 1
fi

# Free the port: kill whatever is currently listening on it.
PIDS=""
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -t -i ":${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
elif command -v ss >/dev/null 2>&1; then
  PIDS="$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
fi

if [ -n "$PIDS" ]; then
  echo "Port ${PORT} is in use by PID(s): ${PIDS//$'\n'/ } — terminating."
  # shellcheck disable=SC2086
  kill $PIDS 2>/dev/null || true
  sleep 1
  # Escalate to SIGKILL for anything that ignored SIGTERM.
  for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
fi

echo "Starting dashboard server on http://localhost:${PORT}/"
echo "Open that URL in your browser. Press Ctrl+C to stop."

cd "$HERE"
exec "$PY" server.py
