#!/usr/bin/env bash
#
# Start the dashboard HTTP server and (optionally) a public trycloudflare tunnel.
# Serves dashboard.html (and stub /api endpoints) on http://localhost:8765/
#
# Usage:
#   ./start.sh           # start HTTP server in the foreground (no tunnel)
#   TUNNEL=1 ./start.sh  # start HTTP server + cloudflare tunnel (prints public URL)
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

cd "$HERE"

if [ "${TUNNEL:-0}" = "1" ]; then
  SERVER_LOG="${SERVER_LOG:-/tmp/dashboard-server.log}"
  : > "$SERVER_LOG"
  "$PY" server.py >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  cleanup() {
    [ -n "${TUNNEL_PID:-}" ] && kill "$TUNNEL_PID" 2>/dev/null || true
    [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  echo "Dashboard server starting in background (PID $SERVER_PID), waiting for port ${PORT}…"
  for i in $(seq 1 30); do
    if python3 - <<PY
import socket
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', int('${PORT}')))
except Exception:
    raise SystemExit(1)
finally:
    s.close()
PY
    then
      break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "ERROR: dashboard server exited early — see $SERVER_LOG"
      wait "$SERVER_PID" || true
      exit 1
    fi
    sleep 1
  done

  if ! python3 - <<PY
import socket
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', int('${PORT}')))
except Exception:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    echo "ERROR: dashboard server did not open port ${PORT} — see $SERVER_LOG"
    exit 1
  fi

  # Optional trycloudflare tunnel.
  # cloudflared lives as a Windows binary (runs via WSL interop).
  CLOUDFLARED="${CLOUDFLARED_BIN:-/home/adamsl/.local/share/cloudflared/cloudflared.exe}"
  if [ -x "$CLOUDFLARED" ]; then
    TUNNEL_LOG="$(mktemp /tmp/cloudflared-tunnel-XXXX.log)"
    "$CLOUDFLARED" tunnel --url "http://127.0.0.1:${PORT}" --no-autoupdate >"$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    echo "Tunnel starting (PID $TUNNEL_PID), waiting for URL…"
    for i in $(seq 1 45); do
      URL="$(python3 - <<'PY' "$TUNNEL_LOG"
import re, sys
path = sys.argv[1]
try:
    text = open(path, 'r', errors='ignore').read()
except FileNotFoundError:
    text = ''
m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', text)
print(m.group(0) if m else '')
PY
      )"
      [ -n "$URL" ] && break
      if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo "ERROR: tunnel exited early — see $TUNNEL_LOG"
        wait "$TUNNEL_PID" || true
        exit 1
      fi
      sleep 1
    done
    if [ -n "$URL" ]; then
      echo "Public URL: $URL"
      echo "$URL" > /tmp/dashboard-public-url.txt
    else
      echo "WARNING: tunnel did not produce a URL within 45s — check $TUNNEL_LOG"
    fi
  else
    echo "WARNING: cloudflared not found at $CLOUDFLARED — skipping tunnel."
  fi

  echo "Open $URL in your browser. Press Ctrl+C to stop."
  wait "$SERVER_PID"
  exit $?
fi

echo "Open http://localhost:${PORT}/ in your browser. Press Ctrl+C to stop."
exec "$PY" server.py
