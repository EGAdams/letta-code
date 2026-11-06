#!/bin/bash
# Verify that edits made to the dashboard are actually being served by the live box.
# Run after any file modification: ./verify-live.sh <marker-string>
# Example: ./verify-live.sh "mazda-objects"
# This catches the "wrong machine" trap where the editing tool modifies a decoy checkout.

set -e

MARKER="${1:?Usage: ./verify-live.sh <marker-string> [url]}"
LIVE_URL="${2:-${VERIFY_LIVE_URL:-http://${VERIFY_LIVE_HOST:-100.102.209.100}:${VERIFY_LIVE_PORT:-8765}/${VERIFY_LIVE_PATH:-dashboard.html}}}"

echo "🔍 Verifying live dashboard contains: $MARKER"

COUNT=$(curl -s "$LIVE_URL" 2>/dev/null | grep -c "$MARKER" || echo "0")

if [ "$COUNT" -gt 0 ]; then
  echo "✅ VERIFIED: Found $COUNT occurrence(s) of '$MARKER' in live dashboard"
  exit 0
else
  echo "❌ FAILED: '$MARKER' NOT found in live dashboard at $LIVE_URL"
  echo "   This likely means the edit was applied to a decoy checkout, not the live machine."
  echo "   Check CLAUDE.md 'Which machine is live' section and use Frita (agent-881a883f-...) for direct access."
  exit 1
fi
