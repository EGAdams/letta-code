#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  run-local-in-dir.sh <target-directory> [mode] [letta args...]

Modes:
  --new-with-id   Create a new conversation, print/log its ID, then open it interactively
  --new-id-only   Create a new conversation and print ONLY the conversation ID, then exit
  (no mode)       Start Letta normally in the target directory

Examples:
  run-local-in-dir.sh /tmp/my-project
  run-local-in-dir.sh /tmp/my-project --agent agent-123
  run-local-in-dir.sh /tmp/my-project --new-with-id --agent agent-123
  run-local-in-dir.sh /tmp/my-project --new-id-only --agent agent-123
EOF
  exit 1
}

log() {
  printf '[run-local-in-dir] %s\n' "$*" >&2
}

if [[ $# -lt 1 ]]; then
  usage
fi

TARGET_DIR="$1"
shift || true

MODE="interactive"
if [[ $# -gt 0 ]]; then
  case "${1}" in
    --new-with-id)
      MODE="new-with-id"
      shift
      ;;
    --new-id-only)
      MODE="new-id-only"
      shift
      ;;
  esac
fi

if [[ ! -d "${TARGET_DIR}" ]]; then
  echo "Error: target directory does not exist: ${TARGET_DIR}" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LETTA_BIN="${REPO_ROOT}/letta.js"
DEFAULT_SERVER_URL="http://100.80.49.10:8283"

if [[ ! -f "${LETTA_BIN}" ]]; then
  echo "Error: local Letta binary not found: ${LETTA_BIN}" >&2
  exit 1
fi

if [[ -z "${LETTA_BASE_URL:-}" ]]; then
  export LETTA_BASE_URL="${DEFAULT_SERVER_URL}"
fi

extract_host_port() {
  local url="$1"
  url="${url#http://}"
  url="${url#https://}"
  local hostport="${url%%/*}"
  local host="${hostport%%:*}"
  local port="${hostport##*:}"
  if [[ "${host}" == "${port}" ]]; then
    if [[ "$1" == https://* ]]; then
      port="443"
    else
      port="80"
    fi
  fi
  printf '%s %s\n' "${host}" "${port}"
}

validate_new_conversation_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --conversation|--conv|--new|-p|--prompt|--input-format|--output-format)
        echo "Error: $1 cannot be used with ${MODE}." >&2
        exit 3
        ;;
    esac
    shift
  done
}

create_conversation_id() {
  python3 - "${LETTA_BIN}" "$@" <<'PY'
import json
import subprocess
import sys

letta_bin = sys.argv[1]
extra_args = sys.argv[2:]

cmd = [
    letta_bin,
    "--input-format", "stream-json",
    "--output-format", "stream-json",
    "--new",
    *extra_args,
]

proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

conversation_id = None
stderr_chunks = []

try:
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue

        if obj.get("type") == "system" and obj.get("subtype") == "init":
            conversation_id = obj.get("conversation_id")
            if conversation_id:
                print(conversation_id)
                break

    if not conversation_id:
        if proc.stderr is not None:
            stderr_chunks.append(proc.stderr.read())
        raise SystemExit(
            "Failed to read conversation_id from Letta startup.\n"
            + "".join(stderr_chunks)
        )
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
PY
}

read -r server_host server_port < <(extract_host_port "${LETTA_BASE_URL}")
if ! nc -z -w 2 "${server_host}" "${server_port}" >/dev/null 2>&1; then
  echo "Error: Letta server is unreachable: ${LETTA_BASE_URL}" >&2
  echo "Network preflight failed for ${server_host}:${server_port}." >&2
  echo "Refusing to start CLI to avoid auth/setup reset loops." >&2
  exit 2
fi

log "building local CLI"
(cd "${REPO_ROOT}" && bun run build)

log "repo: ${REPO_ROOT}"
log "cwd:  ${TARGET_DIR}"
log "server: ${LETTA_BASE_URL}"

cd "${TARGET_DIR}"

case "${MODE}" in
  interactive)
    log "exec: ${LETTA_BIN} $*"
    exec "${LETTA_BIN}" "$@"
    ;;
  new-id-only)
    validate_new_conversation_args "$@"
    CONV_ID="$(create_conversation_id "$@")"
    printf '%s\n' "${CONV_ID}"
    ;;
  new-with-id)
    validate_new_conversation_args "$@"
    CONV_ID="$(create_conversation_id "$@")"
    log "conversation_id: ${CONV_ID}"
    exec "${LETTA_BIN}" --conversation "${CONV_ID}"
    ;;
  *)
    echo "Error: unknown mode ${MODE}" >&2
    exit 4
    ;;
esac