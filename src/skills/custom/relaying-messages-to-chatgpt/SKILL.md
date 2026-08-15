---
name: relaying-messages-to-chatgpt
description: Send a message to a browser-controlled ChatGPT session and get its reply back, via the relay_message_to_chatgpt tool. Use when a task needs ChatGPT's answer relayed into a letta-code or Letta-agent session, when browser_server.py needs to be started/diagnosed, or when relay_message_to_chatgpt returns BROWSER_SERVER_UNREACHABLE / TIMEOUT_ERROR.
---

# Relaying Messages to ChatGPT

## What this is

`relay_message_to_chatgpt` drives a real, already-logged-in Chrome tab open on
chatgpt.com: it types your message, hits send, and polls until the reply
looks stable, then returns the reply plus the full thread. It does not use
any API key — it automates the actual chatgpt.com web UI, so whatever plan
that browser session is authenticated with (e.g. Plus/Pro) is what answers.

Two implementations of the same logic exist, for two different consumers:

| File | Consumer |
|---|---|
| `src/tools/impl/RelayMessageToChatGpt.ts` | The `letta` CLI built from this repo (letta-code) |
| `browser_tools/letta_chatgpt_relay_tool.py` | A Letta agent's directly-attached custom tool (Letta server `POST /tools`) |

Both call the same `browser_server.py` HTTP API, documented in
`browser_tools/API_GUIDE.md`.

## Architecture

```
relay_message_to_chatgpt (tool)
        |
        v
browser_server.py :5001         <- Flask + Selenium/undetected_chromedriver,
  /type  /send  /read_thread       drives a REAL visible Chrome window that
  /health                          is already logged into chatgpt.com
        ^
        | (optional network front door when the caller can't reach :5001 directly)
executor_server.py :8787
```

- **`browser_server.py` must already be running** with a Chrome profile that
  is logged into chatgpt.com. It is not started automatically by the tool.
  Start it with `python browser_server.py` from `browser_tools/` — see that
  directory's `AGENTS.md` for profile/Chrome-binary env vars
  (`CHROME_USER_DATA_DIR`, `CHROME_PROFILE`, `CHROME_BINARY`,
  `CHROME_VERSION_MAIN`).
- The tool tries, in order: an explicit `browser_server_url` arg, then
  `$BROWSER_SERVER_URL`, then `http://127.0.0.1:5001`, `http://localhost:5001`,
  `http://host.docker.internal:5001`, `http://100.80.49.10:5001`.
- If none of those answer `GET /health` directly, it looks for an
  `executor_server.py` (explicit `executor_url` arg, `$EXECUTOR_URL`, then a
  short list of known executor hosts) and routes the same browser calls
  through `POST /run` as `curl` commands — useful when the browser server is
  only reachable from another machine.

## Enabling the tool in a letta-code session

`relay_message_to_chatgpt` is **not** in any default toolset (Anthropic,
Codex, or Gemini) — same as `executor_run`, it is opt-in only, because it
drives a real browser. Passing `--tools` replaces the *entire* toolset (it
does not add to the default), so list everything you also need alongside it,
e.g. to keep the normal Anthropic toolset plus this one:

```bash
letta --tools AskUserQuestion,Bash,TaskOutput,Edit,EnterPlanMode,ExitPlanMode,Glob,Grep,TaskStop,memory,Read,Skill,Task,TodoWrite,Write,relay_message_to_chatgpt
```

For a live Letta agent instead (Scissari/Frita/etc.), attach
`browser_tools/letta_chatgpt_relay_tool.py` directly as a custom tool via the
Letta server's tool-attach flow rather than the CLI `--tools` flag.

## Verifying it works before trusting a result

```bash
curl -sS --max-time 4 http://127.0.0.1:5001/health   # or the relevant host
```

If that fails, the tool will too — it returns
`{"status":"BROWSER_SERVER_UNREACHABLE", ...}` with a `message` listing every
URL it tried and why each failed. That is the *expected, correct* result when
no browser server is up, not a bug — confirmed by running
`src/tools/impl/RelayMessageToChatGpt.ts` directly with no server running.

## Parameters and return shape

See `src/tools/descriptions/RelayMessageToChatGpt.md` (the model-facing tool
description) for the full parameter list and return-shape reference —
`message` is the only required argument; everything else (`timeout_seconds`,
`poll_seconds`, `stability_checks`, `max_total_seconds`, executor/browser
URL overrides) has a working default.

`status` in the returned JSON is one of:
- `ok` — `response` has ChatGPT's stable reply, `thread` has the full turn history
- `TIMEOUT_ERROR` — no stable reply within `timeout_seconds` progress or
  `max_total_seconds` absolute cap; `response` may hold the last partial text
- `BROWSER_SERVER_UNREACHABLE` — no candidate URL (direct or via executor)
  answered `/health`; nothing was sent

## Troubleshooting

- **`BROWSER_SERVER_UNREACHABLE`**: start `browser_server.py` on the machine
  that has the logged-in Chrome profile, or pass `browser_server_url` /
  `executor_url` explicitly if it's on a nonstandard host/port.
- **`TIMEOUT_ERROR` with `response: null`**: ChatGPT never produced a
  non-placeholder reply (still "Thinking..."/"Generating..." at deadline) —
  raise `timeout_seconds`/`max_total_seconds`, or check the Chrome window
  directly for a stuck/errored UI state.
- **Reply looks truncated/stale**: raise `stability_checks` — the tool
  returns as soon as N consecutive polls see identical text, so a slow
  streaming reply with a short `poll_seconds` can look "stable" mid-stream.
