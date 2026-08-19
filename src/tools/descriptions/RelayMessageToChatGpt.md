# relay_message_to_chatgpt

Relay a user message to the controlled ChatGPT browser via browser_server.py, using executor_server.py as the reachable network front door when available. Polls until ChatGPT has finished responding and returns the reply and full conversation thread.

## Overview

This tool connects to a running `browser_server.py` instance that controls a ChatGPT browser session. It:

1. Types your message into the ChatGPT input box
2. Clicks send
3. Polls the `/read_thread` endpoint repeatedly until ChatGPT's reply appears stable
4. Returns the complete response plus conversation history

The tool can work either directly (if the browser server is on localhost) or through an executor server that acts as a network gateway, making it usable from remote environments.

## Parameters

- **message** (required): The user message to send to ChatGPT
- **browser_server_url**: Optional base URL for the browser server (e.g., `http://localhost:5001`). If empty, auto-detects common URLs
- **executor_url**: Optional executor_server.py base URL. If set, all browser API calls route through the executor
- **executor_token**: Optional bearer token for executor_server.py authentication
- **timeout_seconds**: Seconds to wait without response progress before timing out (default 180)
- **poll_seconds**: Seconds between `/read_thread` polling intervals (default 10)
- **stability_checks**: Number of consecutive identical assistant reads confirming the answer is complete (default 2)
- **max_total_seconds**: Absolute cap for the entire relay operation in seconds (default 600)

## Return Value

Returns a JSON string containing:

- **status**: `ok` on success, `TIMEOUT_ERROR` or `BROWSER_SERVER_UNREACHABLE` on failure
- **response**: The ChatGPT assistant's latest reply text (or null if unavailable)
- **thread**: Array of conversation turns with role/text/turn_id
- **turn_count**: Total number of messages in the thread
- **elapsed_seconds**: Time spent in the relay call
- **browser_server_url**: The resolved browser server URL used
- **transport**: Either `"direct"` or `"executor"` depending on how the call was routed
- **message**: Error description if status is not `ok`

## Examples

### Direct local usage

```
relay_message_to_chatgpt("What is the capital of France?")
```

### Remote usage via executor

```
relay_message_to_chatgpt(
  "Explain TypeScript generics",
  executor_url="http://10.0.0.7:8787",
  executor_token="your-token-here"
)
```

### Custom timeouts

```
relay_message_to_chatgpt(
  message="Solve this complex problem...",
  timeout_seconds=300,
  max_total_seconds=900,
  stability_checks=3
)
```

## Requirements

- A running `browser_server.py` instance controlling a ChatGPT browser session
- Network access to the browser server (direct or via executor)
- Optional: A running `executor_server.py` for remote access

## Environment Variables

- `BROWSER_SERVER_URL`: Default browser server URL if not specified
- `EXECUTOR_URL`: Default executor server URL if not specified
- `EXECUTOR_TOKEN`: Default executor bearer token if not specified
