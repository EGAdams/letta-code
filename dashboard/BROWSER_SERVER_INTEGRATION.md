# Browser Server Integration

## Overview

The `browser_server.py` (port 5001) is a Flask application that drives a real Chrome/Chromium window logged into chatgpt.com. It provides an HTTP API for sending messages to ChatGPT and retrieving responses, enabling the `relay_message_to_chatgpt` tool to work with live ChatGPT sessions.

**Two implementations** of the same logic exist:
1. **CLI tool**: `src/tools/impl/RelayMessageToChatGpt.ts` (TypeScript) — for letta CLI and letta-code
2. **Agent tool**: `browser_tools/letta_chatgpt_relay_tool.py` (Python) — for live Letta agents

Both call the same `browser_server.py` HTTP API.

## Architecture

```
relay_message_to_chatgpt (tool in CLI or agent)
        ↓
browser_server.py :5001
  /health  /type  /send  /read_thread
        ↑
  (optional network gateway when unreachable directly)
executor_server.py :8787
```

## Setup

### 1. Ensure Flask and undetected_chromedriver are installed

The browser_server looks for Python environments with these dependencies:

```bash
# Option A: Use BROWSER_SERVER_PYTHON env var
export BROWSER_SERVER_PYTHON=/path/to/python3
python3 browser_tools/browser_server.py

# Option B: Let it auto-discover (checks these in order):
# - $BROWSER_SERVER_PYTHON environment variable
# - ./browser_tools/.venv/bin/python3 (local venv)
# - /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/venv/bin/python3
```

### 2. Chrome profile with ChatGPT login

The browser_server requires a Chrome profile that is **already logged into chatgpt.com**. Configure the profile via environment variables:

```bash
# Use custom Chrome user data directory
export CHROME_USER_DATA_DIR=/path/to/profile

# Or let it use defaults:
# - $CHROME_USER_DATA_DIR if set
# - ~/.config/google-chrome (Chrome's default)
# - ~/.config/google-chrome-browser-server (browser_server's default)
```

Additional Chrome/Chromium configuration (all optional):

```bash
export CHROME_BINARY=/path/to/chrome          # Chrome binary location
export CHROME_PROFILE="Default"                # Profile name within user data dir
export CHROME_VERSION_MAIN=127                 # Chrome major version
export BROWSER_SERVER_ALLOW_TEMP_PROFILE=1    # Allow temporary profiles (for testing)
```

### 3. Start the server

```bash
cd /home/adamsl/letta-code/browser_tools
python3 browser_server.py
```

**Via dashboard**: Visit Server Management tab → click "Start" on "ChatGPT Browser Server" tile.

## API Endpoints

### GET /health
Health check endpoint. Returns `200 OK` when the server and Chrome window are operational.

```bash
curl http://127.0.0.1:5001/health
# Response: {"status": "ok"}
```

### POST /type
Type text into the ChatGPT message input box.

```bash
curl -X POST http://127.0.0.1:5001/type -H "Content-Type: application/json" -d '{"text": "Hello"}'
```

### POST /send
Click the Send button and begin waiting for ChatGPT's response.

```bash
curl -X POST http://127.0.0.1:5001/send
```

### GET /read_thread
Poll to read the latest message thread. Returns conversation history with turn IDs, roles, and text.

```bash
curl 'http://127.0.0.1:5001/read_thread?last=20'
# Response: {"status": "ok", "thread": [{...}, {...}], "turn_count": 5}
```

**Query parameters**:
- `last` (optional, default 20): Number of recent turns to return

## Tool: relay_message_to_chatgpt

### Usage

```bash
# CLI
letta --tools relay_message_to_chatgpt -- -p "What is the capital of France?"

# Agent (send message to FritaAgent)
message=$(cat <<EOF
Use relay_message_to_chatgpt to ask ChatGPT: "Explain quantum computing"
EOF
)
letta --agent agent-881a883f-edd0-4963-bf67-6ef178b8f018 -p "$message"
```

### Parameters

- **message** (required): Text to send to ChatGPT
- **browser_server_url** (optional): Explicit browser server URL (e.g., `http://127.0.0.1:5001`)
- **executor_url** (optional): Executor server URL for remote browser access (e.g., `http://127.0.0.1:8787`)
- **executor_token** (optional): Bearer token for executor authentication
- **timeout_seconds** (optional, default 180): Seconds to wait without progress before timeout
- **poll_seconds** (optional, default 10): Seconds between `/read_thread` polls
- **stability_checks** (optional, default 2): Consecutive identical reads before considering response stable
- **max_total_seconds** (optional, default 600): Absolute cap for entire relay operation

### Return value

JSON string with:

```json
{
  "status": "ok",                    // "ok" | "TIMEOUT_ERROR" | "BROWSER_SERVER_UNREACHABLE"
  "response": "The capital of...",   // ChatGPT's reply (or null if error)
  "thread": [{...}],                 // Full conversation history
  "turn_count": 5,                   // Number of messages in thread
  "elapsed_seconds": "12.3",
  "browser_server_url": "http://127.0.0.1:5001",
  "transport": "direct",             // "direct" or "executor"
  "message": "error description"      // Only when status != "ok"
}
```

### URL auto-discovery

The tool searches for browser_server at these URLs (in order):

1. Explicit `browser_server_url` parameter
2. `$BROWSER_SERVER_URL` environment variable
3. `http://127.0.0.1:5001` (localhost)
4. `http://localhost:5001`
5. `http://host.docker.internal:5001` (Docker bridge)
6. `http://100.80.49.10:5001` (network)

If none answer `/health` directly, it attempts to route through `executor_server.py`.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `BROWSER_SERVER_UNREACHABLE` | Browser server not running or not reachable | Start browser_server; verify `/health` responds on port 5001 |
| `TIMEOUT_ERROR` with `response: null` | ChatGPT still thinking at deadline | Increase `timeout_seconds`/`max_total_seconds` or check Chrome window directly |
| Response looks truncated or stale | Streaming reply detected as stable mid-stream | Increase `stability_checks` or `poll_seconds` |
| Chrome window not visible | server started but browser not opening | Check `CHROME_BINARY` and `CHROME_USER_DATA_DIR` env vars; ensure Chrome is installed |
| "Missing Python dependency" error | Flask or undetected_chromedriver not installed | Set `BROWSER_SERVER_PYTHON` to a Python environment with both packages |

## Files

| Path | Purpose |
|------|---------|
| `browser_tools/browser_server.py` | Flask server implementation; provides `/health`, `/type`, `/send`, `/read_thread` endpoints |
| `browser_tools/API_GUIDE.md` | Full HTTP API documentation for browser_server |
| `src/tools/impl/RelayMessageToChatGpt.ts` | CLI tool implementation (TypeScript) |
| `src/tools/descriptions/RelayMessageToChatGpt.md` | User-facing documentation |
| `browser_tools/letta_chatgpt_relay_tool.py` | Agent tool implementation (Python, for live Letta agents) |
| `src/skills/custom/relaying-messages-to-chatgpt/SKILL.md` | Comprehensive skill documentation |

## Dashboard Integration

The dashboard Server Management tab monitors `browser-server`:

- **Tile**: "ChatGPT Browser Server"
- **Health URL**: `http://127.0.0.1:5001/health`
- **Status**: Red (offline) | Green (running)
- **Restart**: Calls `start_browser_server()` function in `dashboard/server.py`

To start: Click "Start" button on the ChatGPT Browser Server tile in Server Management tab.

## Related

- Skill: `relaying-messages-to-chatgpt` — orchestrates browser_server setup and relay_message_to_chatgpt usage
- Frita Agent: Uses relay_message_to_chatgpt tool; can provide guidance on browser_server status
- Executor Server: Acts as network gateway when browser_server not directly reachable (`:8787`)
