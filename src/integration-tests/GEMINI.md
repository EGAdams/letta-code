# Letta Code Integration Tests

This directory contains the integration test suite for the `letta-code` CLI tool. These tests ensure the CLI functions correctly by spawning real processes and interacting with the Letta API.

## Project Overview

The integration tests verify various aspects of the `letta-code` CLI, including:
- **Startup Flow:** Validating CLI flags like `--agent`, `--conversation`, and `--new-agent`.
- **Agent Interactions:** Testing specific agent behaviors (e.g., the Scissari agent).
- **Headless Formats:** Ensuring correct input/output handling for headless environments.
- **Approval Recovery:** Testing the ability to recover from interrupted approval flows.
- **OAuth Health:** Checking the health of OAuth integrations.

### Main Technologies
- **Runtime:** [Bun](https://bun.sh/)
- **Test Runner:** `bun:test`
- **Language:** TypeScript
- **Process Management:** `node:child_process` (spawning the CLI under test)
- **Logging:** Custom `RemoteLogger` for external test state tracking.

## Building and Running

### Environment Variables
The tests require several environment variables to be set:
- `LETTA_API_KEY`: Required for most integration tests to authenticate with the Letta API.
- `LETTA_BASE_URL`: (Optional) The base URL for the Letta API. Defaults to a hardcoded IP if not provided.
- `LETTA_RUN_SCISSARI_TEST`: Set to `1` to enable Scissari agent tests.
- `LETTA_LOGGER_RESET_API`: (Optional) URL for the logger reset API.
- `LETTA_CODE_AGENT_ROLE`: Usually set to `subagent` within tests to avoid polluting user settings.

### Key Commands
- **Run all tests:**
  ```bash
  bun test
  ```
- **Run a specific test file:**
  ```bash
  bun test startup-flow.integration.test.ts
  ```
- **Clear remote loggers:**
  ```bash
  bun clear-loggers.ts
  ```
- **Run CLI in development mode (as tests do):**
  ```bash
  bun run dev [args]
  ```

## Development Conventions

### Test Structure
- **File Naming:** Integration tests should end with `.integration.test.ts` or `.test.ts`.
- **Isolation:** Use `beforeEach` to call `resetAllLoggers()` to ensure a clean state for every test.
- **Process Spawning:** Use the `runCli` helper function found in most test files to spawn the CLI. This helper handles timeouts, retries, and captures stdout/stderr.
- **Logging:** Use `RemoteLogger` to provide visibility into test progress, especially for long-running or complex integration scenarios.

### Logger Helpers
- `ALL_LOGGER_IDS`: A registry of all logger IDs used across tests, found in `logger-helpers.ts`.
- `resetAllLoggers()`: Clears all registered loggers via a remote API.

### Common Patterns
- **JSON Parsing:** Many tests use `--output-format json` and parse the CLI's stdout to verify properties like `agent_id` and `conversation_id`.
- **Normalization:** Log messages are often normalized (see `normalizeLoggerMessage` in test files) to provide consistent status updates (e.g., mapping `PASS` to `finished`).
