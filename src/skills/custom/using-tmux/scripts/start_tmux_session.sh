#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: start_tmux_session.sh [options]

Starts a detached tmux session that runs a command, logs output, and prints follow-up commands.

Options:
  --session NAME     tmux session name (default: process_e2e)
  --cwd PATH         working directory to cd into before running command
                     (default: /home/adamsl/rol_finances)
  --cmd COMMAND      command to run inside the session (required)
  --log PATH         log file path
                     (default: /home/adamsl/rol_finances/readable_documents/reports/process_run_<timestamp>.log)
  --py-path PATH     optional PYTHONPATH value to export before running command
  --restart          kill existing session with same name before starting
  -h, --help         show this help message

Examples:
  start_tmux_session.sh --cmd "python -m app.run"
  start_tmux_session.sh --session my_job --cwd /tmp/project --cmd "./run.sh" --restart
EOF
}

timestamp="$(date +%Y%m%d_%H%M%S)"
session="process_e2e"
cwd="/home/adamsl/rol_finances"
cmd=""
log_file="/home/adamsl/rol_finances/readable_documents/reports/process_run_${timestamp}.log"
py_path=""
restart=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --session)
      [[ $# -ge 2 ]] || { echo "Error: --session requires a value." >&2; usage; exit 1; }
      session="$2"
      shift 2
      ;;
    --cwd)
      [[ $# -ge 2 ]] || { echo "Error: --cwd requires a value." >&2; usage; exit 1; }
      cwd="$2"
      shift 2
      ;;
    --cmd)
      [[ $# -ge 2 ]] || { echo "Error: --cmd requires a value." >&2; usage; exit 1; }
      cmd="$2"
      shift 2
      ;;
    --log)
      [[ $# -ge 2 ]] || { echo "Error: --log requires a value." >&2; usage; exit 1; }
      log_file="$2"
      shift 2
      ;;
    --py-path)
      [[ $# -ge 2 ]] || { echo "Error: --py-path requires a value." >&2; usage; exit 1; }
      py_path="$2"
      shift 2
      ;;
    --restart)
      restart=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: Unknown option '$1'." >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$cmd" ]]; then
  echo "Error: --cmd is required." >&2
  usage
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "Error: tmux is not installed or not in PATH." >&2
  exit 1
fi

if $restart; then
  if tmux has-session -t "$session" 2>/dev/null; then
    tmux kill-session -t "$session"
  fi
fi

if tmux has-session -t "$session" 2>/dev/null; then
  echo "Error: tmux session '$session' already exists. Use --restart to replace it." >&2
  exit 1
fi

mkdir -p "$(dirname "$log_file")"

printf -v q_cwd '%q' "$cwd"
printf -v q_log '%q' "$log_file"

runner_script="cd ${q_cwd}"

if [[ -n "$py_path" ]]; then
  printf -v q_py_path '%q' "$py_path"
  runner_script+=" && export PYTHONPATH=${q_py_path}"
fi

runner_script+=" && ${cmd} 2>&1 | tee -a ${q_log}"

printf -v q_runner '%q' "$runner_script"

tmux new-session -d -s "$session" "bash -lc ${q_runner}"

echo "Started tmux session '$session'."
echo "Attach: tmux attach -t $session"
echo "Tail log: tail -f $log_file"

