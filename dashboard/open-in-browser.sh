#!/usr/bin/env bash
#
# Wait for the dashboard server to come up, then open it in a browser window.
# Run on login via the dashboard-browser.service systemd --user unit.
#
set -uo pipefail

URL="http://localhost:8765/"
LOG_FILE="/tmp/dashboard-browser-launch.log"

echo "$(date -Is) waiting for $URL ..." >>"$LOG_FILE"

for _ in $(seq 1 90); do
  if curl -sf -o /dev/null "$URL"; then
    echo "$(date -Is) dashboard is up — opening browser" >>"$LOG_FILE"
    exec google-chrome --new-window --app="$URL" >>"$LOG_FILE" 2>&1
  fi
  sleep 2
done

echo "$(date -Is) dashboard never became healthy at $URL — not opening browser" >>"$LOG_FILE"
exit 1
