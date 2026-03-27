#!/usr/bin/env bash
set -euo pipefail

BRIDGE="/home/adamsl/rol_finances/tools/integration_bridge/nonprofit_finance_ingest_bridge.py"
PYTHON_BIN="/home/adamsl/planner/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: python not found or not executable: $PYTHON_BIN" >&2
  exit 2
fi

if [ ! -f "$BRIDGE" ]; then
  echo "ERROR: bridge script not found: $BRIDGE" >&2
  exit 2
fi

"$PYTHON_BIN" "$BRIDGE" "$@"
