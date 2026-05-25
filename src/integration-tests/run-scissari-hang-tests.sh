#!/bin/bash
# Run Scissari hang detection integration tests with proper environment setup

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Default values
LETTA_BASE_URL="${LETTA_BASE_URL:-http://100.80.49.10:8283}"
LETTA_API_KEY="${LETTA_API_KEY:-6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8}"

echo "🔍 Scissari Hang Detection Tests"
echo "================================"
echo ""
echo "Environment:"
echo "  LETTA_BASE_URL: $LETTA_BASE_URL"
echo "  LETTA_API_KEY: ${LETTA_API_KEY:0:8}..."
echo "  LETTA_RUN_SCISSARI_TEST: 1 (required)"
echo ""
echo "Log Viewer: http://localhost:8080"
echo "  - ScissariPlanningModeHang_2026"
echo "  - ScissariInactivityTimeout_2026"
echo ""

# Export environment variables for the test
export LETTA_BASE_URL
export LETTA_API_KEY
export LETTA_RUN_SCISSARI_TEST=1

# Run the tests
echo "Starting tests..."
bun test src/integration-tests/scissari-planning-mode-hang.integration.test.ts

echo ""
echo "✓ Test run complete. Check http://localhost:8080 for detailed logs."
