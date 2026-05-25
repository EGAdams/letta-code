# Scissari Telegram No-Reply Pattern

## Problem

Scissari's system prompt instructs her to reply with `<no-reply/>` for simple greetings,
short acknowledgments, and messages not clearly directed at her. When a Telegram→Letta
bridge sends raw user messages (e.g. "hi", "hello"), Scissari treats them as casual chat
and stays silent — even though the user is waiting for a reply.

## Root cause

Without channel context, Scissari cannot tell the difference between:
- a direct Telegram message expecting a real response
- a group chat message she should ignore

## Fix: inject channel context in every message

Wrap the user's message before sending to the Letta API:

```python
wrapped = f"[Telegram DM from @{username}]: {user_message}"
```

This gives Scissari enough context to recognise it as a direct message and respond.

## Diagnosis

In the Telegram bot logs, the symptom is:
```
INFO - Scissari replied with no-reply for message from EG
```

This means the Letta API call **succeeded** — Scissari received the message and made a
deliberate choice to not reply. It is NOT a connectivity, Tailscale, or server problem.

Do not restart the Letta server or check Tailscale when this log line appears.

## Bot location

```
/home/adamsl/codex_test_agent/claude-agent-sdk-demos/telegram_integration/letta_telegram_bot.py
```

The prefix is applied in `send_to_scissari()`.
