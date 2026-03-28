#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <target-directory> [letta args...]" >&2
  echo "Example: $0 /tmp/my-project --new" >&2
  exit 1
fi

TARGET_DIR="$1"
shift || true

if [[ ! -d "${TARGET_DIR}" ]]; then
  echo "Error: target directory does not exist: ${TARGET_DIR}" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
bun run build
LETTA_BIN="${REPO_ROOT}/letta.js"
DEFAULT_SERVER_URL="http://10.0.0.143:8283"

if [[ ! -f "${LETTA_BIN}" ]]; then
  echo "Error: local Letta binary not found: ${LETTA_BIN}" >&2
  exit 1
fi

# Force self-hosted server unless caller already provided LETTA_BASE_URL.
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

read -r server_host server_port < <(extract_host_port "${LETTA_BASE_URL}")
if ! nc -z -w 2 "${server_host}" "${server_port}" >/dev/null 2>&1; then
  echo "Error: Letta server is unreachable: ${LETTA_BASE_URL}" >&2
  echo "Network preflight failed for ${server_host}:${server_port}." >&2
  echo "Refusing to start CLI to avoid auth/setup reset loops." >&2
  exit 2
fi

echo "[run-local-in-dir] repo: ${REPO_ROOT}"
echo "[run-local-in-dir] cwd:  ${TARGET_DIR}"
echo "[run-local-in-dir] server: ${LETTA_BASE_URL}"
echo "[run-local-in-dir] exec: ${LETTA_BIN} $*"

cd "${TARGET_DIR}"
exec "${LETTA_BIN}" "$@"
