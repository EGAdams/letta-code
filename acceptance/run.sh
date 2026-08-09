#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/acceptance"
IR_DIR="$BUILD_DIR/ir"
GENERATED_DIR="$BUILD_DIR/generated"
APS_DIR="${APS_DIR:-$ROOT_DIR/.cache/acceptance-pipeline-specification}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "$APS_DIR/bb.edn" ]]; then
  "$ROOT_DIR/acceptance/install-aps.sh" "$APS_DIR"
fi

mkdir -p "$IR_DIR" "$GENERATED_DIR"
for feature in "$ROOT_DIR"/features/*.feature; do
  stem="$(basename "$feature" .feature)"
  ir="$IR_DIR/$stem.json"
  bb --config "$APS_DIR/bb.edn" gherkin-parser "$feature" "$ir"
  bb acceptance-entrypoint-generator "$ir" "$GENERATED_DIR"
done

export PYTHONPATH="$ROOT_DIR/dashboard:$ROOT_DIR/acceptance"
for generated_test in "$GENERATED_DIR"/*_acceptance_test.py; do
  "$PYTHON_BIN" "$generated_test"
done
