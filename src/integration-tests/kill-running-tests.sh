#!/usr/bin/env bash
set -euo pipefail

PIDFILE_GLOB="${LETTA_INTEGRATION_TEST_PIDFILE_GLOB:-/tmp/letta-integration-tests.*.pid}"

kill_pidfile() {
  local pidfile="$1"
  local pid=""
  local pgid=""

  if [[ ! -f "$pidfile" ]]; then
    return 0
  fi

  read -r pid pgid < "$pidfile" || true
  if [[ -z "${pid:-}" ]]; then
    rm -f "$pidfile"
    return 0
  fi

  if [[ -z "${pgid:-}" ]]; then
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
  fi

  if [[ -n "${pgid:-}" ]]; then
    kill -- "-$pgid" 2>/dev/null || true
  fi
  kill "$pid" 2>/dev/null || true

  sleep 1

  if [[ -n "${pgid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
  fi
  kill -KILL "$pid" 2>/dev/null || true

  rm -f "$pidfile"
}

shopt -s nullglob
pidfiles=( $PIDFILE_GLOB )

if [[ ${#pidfiles[@]} -eq 0 ]]; then
  echo "No integration-test pidfiles found at ${PIDFILE_GLOB}"
else
  for pidfile in "${pidfiles[@]}"; do
    echo "Killing integration test process from ${pidfile}"
    kill_pidfile "$pidfile"
  done
fi

pgrep -af 'bun test src/integration-tests|bun run dev .*src/integration-tests' 2>/dev/null || true
