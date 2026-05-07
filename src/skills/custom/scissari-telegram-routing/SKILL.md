---
name: scissari-telegram-routing
description: Use the current Scissari Telegram path through @scissaribot and the local lettabot instance, verify pairing and chat reachability, distinguish inbound Telegram delivery from outbound bot sends or direct Letta API prompts, and fall back to the real local API on port 8091 when SDK streams drop continuation metadata.
---

# Scissari Telegram Routing

Use this skill when the task mentions Scissari, `@scissaribot`, Telegram delivery, Telegram pairing, or sending a message to Scissari through the Telegram channel.

## Current route

The live Scissari Telegram path is the `lettabot` setup at:

```text
/home/adamsl/lettabot
```

Do not assume the older Python bridge under `claude-agent-sdk-demos` is the active path.

If the direct client/API path is flaky, `lettabot` is the operational fallback, not the legacy Python bridge.

## What we verified

- `@scissaribot` is currently served by `lettabot`
- `lettabot.log` showed:
  - `Bot started as @scissaribot`
  - `DM policy: pairing`
  - `Server: http://100.80.49.10:8283`
  - inbound Telegram traffic from chat `8347775175`
- the old Python log path `/tmp/scissari-telegram.log` was absent during the check
- `python3 src/skills/custom/scissari-hailey-pairing/scripts/ensure_pair_tools.py --dry-run` confirmed Scissari and Hailey both had:
  - `executor_run`
  - `send_message_to_agent_and_wait_for_reply`
  - `send_message_to_agent_async`
  - `web_fetch_exa`
  - `web_search_exa`

## Important distinction

There are three different paths that are easy to confuse:

1. **Inbound Telegram to Scissari**
   - A human messages `@scissaribot`
   - `lettabot` receives the Telegram event
   - Scissari answers inside the Telegram conversation

2. **Outbound bot send to Telegram**
   - A local tool or CLI sends a message *to* a Telegram chat using the bot token
   - This does not simulate a human inbound message to Scissari
   - It is useful for notifications, not for testing Scissari's Telegram intake path

3. **Direct Letta API / local API prompt**
   - `POST /api/v1/chat` to the real local API on `http://127.0.0.1:8091`
   - This bypasses Telegram channel context
   - Use it for agent health checks, not as proof that Telegram routing works

If the SDK drops `approval_request_message`, `stop_reason`, or chunks `tool_call` arguments, prefer the `lettabot` logs plus the direct `8091` API check over the raw client stream.

## Pairing workflow

`@scissaribot` currently uses:

```text
DM policy: pairing
```

So a new Telegram DM may need approval before normal chat works.

Approve a pairing code with:

```bash
cd /home/adamsl/lettabot
lettabot pairing approve telegram <CODE>
```

If the user reports:

```text
failed to initialize session – no init message received
```

start with the pairing flow and `lettabot` logs, not the legacy Python bridge.

## Fast checks

Check recent Telegram activity:

```bash
tail -80 /home/adamsl/lettabot/lettabot.log
```

Look for:

- `Message from <chat_id>: ...`
- `Stream result: success=true`

Check Scissari/Hailey tool parity before asking Scissari to relay to Hailey:

```bash
python3 /home/adamsl/letta-code/src/skills/custom/scissari-hailey-pairing/scripts/ensure_pair_tools.py --dry-run
```

Check the real local API on port `8091` when you need to confirm the live client path:

```bash
curl -s http://127.0.0.1:8091/api/v1/chat
```

## Do not assume these are enough

- `curl https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates`
  - This can return an empty result even when the live `lettabot` path is healthy
- `POST http://127.0.0.1:8080/api/v1/chat`
  - This is the old local-port assumption; prefer `8091` for the real API check
- `lettabot-message send --channel telegram --chat <id>`
  - This sends outbound bot traffic; it does not recreate a user DM into Scissari

## Related skills

- `scissari-hailey-pairing`
- `operating-letta-across-machines`
- `reliable-agent-messaging`
