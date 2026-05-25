#!/usr/bin/env bash
# Syncs src/skills/custom/ and ~/.letta/agents/ from this machine to mom's machine (rosemary46).
# Skips directories that already exist on the target — never overwrites.
# Usage: bash sync_skills.sh [--dry-run]

set -euo pipefail

REMOTE_HOST="100.72.34.38"
REMOTE_USER="adamsl"
REMOTE="$REMOTE_USER@$REMOTE_HOST"
LOCAL_SKILLS_DIR="/home/adamsl/letta-code/src/skills/custom"
REMOTE_SKILLS_DIR="~/letta-code/src/skills/custom"
LOCAL_AGENTS_DIR="$HOME/.letta/agents"
REMOTE_AGENTS_DIR="~/.letta/agents"
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

# Check connectivity
if ! ssh $SSH_OPTS "$REMOTE" true 2>/dev/null; then
  echo "ERROR: Cannot reach $REMOTE_HOST. Is mom's WSL running?"
  exit 1
fi

sync_dirs() {
  local label="$1"
  local local_dir="$2"
  local remote_dir="$3"

  echo ""
  echo "=== Syncing $label ==="

  LOCAL_ITEMS=$(ls "$local_dir" | sort)
  REMOTE_ITEMS=$(ssh $SSH_OPTS "$REMOTE" "ls $remote_dir 2>/dev/null" | sort)

  MISSING=$(comm -23 <(echo "$LOCAL_ITEMS") <(echo "$REMOTE_ITEMS"))

  if [[ -z "$MISSING" ]]; then
    echo "  Nothing to copy — already in sync."
    return
  fi

  while IFS= read -r item; do
    echo -n "  $item ... "
    if $DRY_RUN; then
      echo "[dry-run]"
    else
      rsync -a --quiet "$local_dir/$item" "$REMOTE:$remote_dir/"
      echo "copied"
    fi
  done <<< "$MISSING"
}

# Sync skills
sync_dirs "custom skills" "$LOCAL_SKILLS_DIR" "$REMOTE_SKILLS_DIR"

# Sync agents (skip command-runner.md separately since it's a file not a dir)
echo ""
echo "=== Syncing agents ==="

LOCAL_AGENTS=$(ls "$LOCAL_AGENTS_DIR" | sort)
REMOTE_AGENTS=$(ssh $SSH_OPTS "$REMOTE" "ls $REMOTE_AGENTS_DIR 2>/dev/null" | sort)
MISSING_AGENTS=$(comm -23 <(echo "$LOCAL_AGENTS") <(echo "$REMOTE_AGENTS"))

if [[ -z "$MISSING_AGENTS" ]]; then
  echo "  Nothing to copy — already in sync."
else
  while IFS= read -r item; do
    echo -n "  $item ... "
    if $DRY_RUN; then
      echo "[dry-run]"
    else
      rsync -a --quiet "$LOCAL_AGENTS_DIR/$item" "$REMOTE:$REMOTE_AGENTS_DIR/"
      echo "copied"
    fi
  done <<< "$MISSING_AGENTS"
fi

echo ""
echo "Done."
