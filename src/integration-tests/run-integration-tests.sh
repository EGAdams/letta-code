#!/usr/bin/env bash
set -euo pipefail

# Shared integration-test environment.
# Override any of these before invoking the script if you need a different target.
export LETTA_BASE_URL="${LETTA_BASE_URL:-http://100.80.49.10:8283}"
export LETTA_API_KEY="${LETTA_API_KEY:-6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8}"
export LETTA_CODE_AGENT_ROLE="${LETTA_CODE_AGENT_ROLE:-subagent}"
export LETTA_LOGGER_RESET_API="${LETTA_LOGGER_RESET_API:-http://100.80.49.10:8284/libraries/local-php-api}"
export LETTA_LOGGER_AUTO_RESET="${LETTA_LOGGER_AUTO_RESET:-0}"
export LETTA_LOGGER_RESET_DISABLED="${LETTA_LOGGER_RESET_DISABLED:-0}"
export LETTA_LOGGER_RESET_TIMEOUT_MS="${LETTA_LOGGER_RESET_TIMEOUT_MS:-15000}"
export LETTA_LOGGER_RESET_CONCURRENCY="${LETTA_LOGGER_RESET_CONCURRENCY:-4}"
export LETTA_LOGGER_VIEWER_BASE="${LETTA_LOGGER_VIEWER_BASE:-http://100.80.49.10:8284}"

# Enable the gated integration tests so this runs the full suite in src/integration-tests.
export LETTA_RUN_SCISSARI_TEST="${LETTA_RUN_SCISSARI_TEST:-1}"
export LETTA_RUN_PRESTREAM_APPROVAL_RECOVERY_TEST="${LETTA_RUN_PRESTREAM_APPROVAL_RECOVERY_TEST:-1}"
export LETTA_RUN_TOOL_ATTACH_TEST="${LETTA_RUN_TOOL_ATTACH_TEST:-1}"
export LETTA_RUN_LETTABOT_TEST="${LETTA_RUN_LETTABOT_TEST:-1}"

PIDFILE="${LETTA_INTEGRATION_TEST_PIDFILE:-$(mktemp /tmp/letta-integration-tests.XXXXXX.pid)}"
export LETTA_INTEGRATION_TEST_PIDFILE="$PIDFILE"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  rm -f "$PIDFILE"
}
trap cleanup EXIT

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

printf 'LETTA_LOGGER_RESET_API set to: %s\n' "$LETTA_LOGGER_RESET_API"

printf 'Clearing logviewer loggers once before test run...\n'
bun run "$SCRIPT_DIR"/clear-loggers.ts

bun test "$SCRIPT_DIR"/*.test.ts "$SCRIPT_DIR"/*.integration.test.ts "$@" &
TEST_PID=$!
printf '%s\n' "$TEST_PID" > "$PIDFILE"
wait "$TEST_PID"
