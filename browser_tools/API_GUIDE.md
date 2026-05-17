# Browser Server API Guide

This guide provides the `curl` command syntax for the browser automation server running on `http://127.0.0.1:5001`.

## Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Check server and browser status. |
| `POST` | `/open` | Navigate to a specific URL. |
| `POST` | `/new_chat` | Navigate to the default ChatGPT start page. |
| `POST` | `/type` | Type text into a prompt or specific selector. |
| `POST` | `/send` | Press Enter in the prompt area to send a message. |
| `GET` | `/get_response` | Retrieve the last assistant message. |
| `GET` | `/read_thread` | Retrieve the full conversation history. |
| `GET` | `/screenshot` | Capture a screenshot of the current page. |
| `POST` | `/quit` | Terminate the browser session and clean up. |

---

## Detailed Usage

### 1. Health Check
Checks if the Flask server is up and whether a Chrome instance is currently controlled or available via debugger.
```bash
curl http://127.0.0.1:5001/health
```

### 2. Open URL
Navigates the browser to the provided URL.
- **Body**: `{"url": "string"}` (Optional, defaults to ChatGPT)
```bash
curl -X POST http://127.0.0.1:5001/open \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://www.google.com"}'
```

### 3. New Chat
Resets the browser to the ChatGPT home page.
```bash
curl -X POST http://127.0.0.1:5001/new_chat
```

### 4. Type Text
Types text into the ChatGPT prompt or a specific CSS selector.
- **Body**: 
    - `text`: The string to type.
    - `selector`: (Optional) A CSS selector to target a specific element.
```bash
curl -X POST http://127.0.0.1:5001/type \
     -H 'Content-Type: application/json' \
     -d '{"text":"What is the capital of France?"}'
```

### 5. Send Message
Simulates pressing the `Enter` key on the prompt textarea to submit your input.
```bash
curl -X POST http://127.0.0.1:5001/send
```

### 6. Get Last Response
Retrieves the text content of the very last message sent by the assistant.
```bash
curl http://127.0.0.1:5001/get_response
```

### 7. Read Conversation Thread
Returns the full conversation as a list of turns containing role, turn ID, and text.
- **Query Param**: `last=N` (Optional, returns only the most recent N turns).
```bash
# Fetch full thread
curl http://127.0.0.1:5001/read_thread

# Fetch last 2 turns
curl http://127.0.0.1:5001/read_thread?last=2
```

### 8. Take Screenshot
Saves a screenshot of the current browser view to `screenshot.png` on the server's local directory.
```bash
curl http://127.0.0.1:5001/screenshot
```

### 9. Quit Browser
Closes the browser instance, kills the process, and cleans up temporary profiles.
```bash
curl -X POST http://127.0.0.1:5001/quit
```

## Error Codes

- `200 OK`: Request successful.
- `500 Internal Server Error`: WebDriver or system error occurred.
- `504 Gateway Timeout`: The operation timed out (e.g., page didn't load or element wasn't found).

## Development Notes
- The server defaults to port `5001`.
- If using ChatGPT, ensure you are logged in within the browser session if a persistent profile is configured.
- For headless or remote environments, ensure `CHROME_BINARY` and `CHROME_USER_DATA_DIR` are set correctly in your environment variables.