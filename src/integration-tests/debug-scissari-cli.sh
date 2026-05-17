#!/bin/bash
# Diagnostic script to test if the Scissari CLI is working

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

SCISSARI_AGENT_ID="agent-5955b0c2-7922-4ffe-9e43-b116053b80fa"
LETTA_BASE_URL="${LETTA_BASE_URL:-http://100.80.49.10:8283}"
LETTA_API_KEY="${LETTA_API_KEY:-6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8}"

echo "🔍 Scissari CLI Diagnostic"
echo "=========================="
echo ""
echo "Environment:"
echo "  LETTA_BASE_URL: $LETTA_BASE_URL"
echo "  LETTA_API_KEY: ${LETTA_API_KEY:0:8}..."
echo "  SCISSARI_AGENT_ID: $SCISSARI_AGENT_ID"
echo ""

echo "Step 1: Building the project..."
bun run build 2>&1 | tail -5
echo "✓ Build complete"
echo ""

echo "Step 2: Testing basic CLI functionality (simple prompt)..."
echo "Running: bun run dev -m gpt-5.3-codex -p 'Say OK' --output-format json"
timeout 30 bun run dev \
  -m gpt-5.3-codex \
  -p "Say OK" \
  --output-format json \
  2>&1 | head -50 || {
  EXIT_CODE=$?
  if [ $EXIT_CODE -eq 124 ]; then
    echo "⚠️  Basic test TIMEOUT after 30 seconds"
  else
    echo "❌ Basic test failed with exit code $EXIT_CODE"
  fi
}
echo ""

echo "Step 3: Testing Scissari agent directly (stream-json format)..."
echo "Running: bun run dev --agent $SCISSARI_AGENT_ID --new -p 'Hello' --output-format stream-json"
timeout 30 bun run dev \
  --agent "$SCISSARI_AGENT_ID" \
  --new \
  -p "Hello" \
  --output-format stream-json \
  --memfs-startup skip \
  2>&1 | head -50 || {
  EXIT_CODE=$?
  if [ $EXIT_CODE -eq 124 ]; then
    echo "⚠️  Scissari test TIMEOUT after 30 seconds"
  else
    echo "❌ Scissari test failed with exit code $EXIT_CODE"
  fi
}
echo ""

echo "✓ Diagnostic complete. Check output above for errors."
