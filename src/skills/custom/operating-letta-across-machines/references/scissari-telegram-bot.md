# Scissari Telegram Bot

## Current status

As of May 2026, the live `@scissaribot` path is the `lettabot` setup in
`/home/adamsl/lettabot`, not the older standalone Python bridge.

The Python bridge notes below are still useful as legacy context, but do not assume they
describe the running production path.

## Current live path

| Item | Value |
|------|-------|
| Telegram bot | `@scissaribot` |
| Live stack | `/home/adamsl/lettabot` |
| Start command | `cd /home/adamsl/lettabot && ./start_scissari_bot.sh` |
| Local API | `http://127.0.0.1:8091` |
| Letta server | `http://100.80.49.10:8283` |
| Agent ID | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |
| DM policy | `pairing` |
| Log file | `/home/adamsl/lettabot/lettabot.log` |

Recent live evidence:

- `lettabot.log` showed `Bot started as @scissaribot`
- `lettabot.log` showed `DM policy: pairing`
- `lettabot.log` showed inbound Telegram traffic from chat `8347775175`
- the old `/tmp/scissari-telegram.log` file did not exist
- `getUpdates` on the bot token returned an empty result during this check, so do not rely on Bot API polling output alone to prove inactivity

## Known continuation failure

We learned a specific failure mode while debugging the Telegram/Hailey handoff path:

- the local CLI had to stay pinned to the checked-out `letta-code` runtime, not a global or stale install
- the SDK/client layer could drop `approval_request_message` and `stop_reason`, which made the run look complete even though the continuation boundary never reached the client
- some `tool_call` payloads arrived with tokenized `arguments`, so the client fallback had to reassemble them before dispatch
- the operational fallback was `lettabot`, with the real local API verified on port `8091`

If this pattern returns, treat `lettabot.log` and the `8091` API as the source of truth before assuming Telegram itself is broken.

## What to use first

If the task is about current Telegram communication with Scissari, start with:

1. `/home/adamsl/lettabot/lettabot.log`
2. `/home/adamsl/rol_finances/skills/scissari-pairing/SKILL.md`
3. `/home/adamsl/letta-code/src/skills/custom/scissari-telegram-routing/SKILL.md`

## Legacy Python bridge

This was the older `@scissaribot` bridge path that sent Telegram messages to Scissari via
the Letta REST API.

## Key facts

| Item | Value |
|------|-------|
| Telegram bot | `@scissaribot` |
| Token env var | `TELEGRAM_TOKEN` in `~/.letta/.env` |
| Scissari agent ID | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |
| Letta API URL | `http://100.80.49.10:8283` (from Windows 11 WSL) or `http://10.0.0.143:8283` (local WiFi) or `localhost:8283` (from Windows 10 Docker host) |
| Bot script | `/home/adamsl/codex_test_agent/claude-agent-sdk-demos/telegram_integration/letta_telegram_bot.py` |
| Python venv | `/home/adamsl/codex_test_agent/claude-agent-sdk-demos/.venv` |
| Log file | `/tmp/scissari-telegram.log` |

Treat this path as legacy unless you have explicit evidence it is the one currently running.

## Start command

```bash
cd /home/adamsl/codex_test_agent/claude-agent-sdk-demos
nohup .venv/bin/python -u telegram_integration/letta_telegram_bot.py >> /tmp/scissari-telegram.log 2>&1 &
```

## Check if running

```bash
ps aux | grep letta_telegram_bot | grep -v grep
tail -20 /tmp/scissari-telegram.log
```

If the process is missing and `/tmp/scissari-telegram.log` does not exist, the bot is simply not running yet.
If the log is empty immediately after startup, wait for the first Telegram event before treating that as a failure.

## Stop it

```bash
pkill -f letta_telegram_bot.py
```

## The wrong bot — do not use

`@government_shutdown_bot` uses the OpenAI Codex SDK (not Letta). It lives at:
`/home/adamsl/codex_test_agent/codex-telegram-coding-assistant/`
and its token is in that directory's `.env`. Starting it does nothing for Scissari.

## Voice message support

The bot transcribes Android voice messages (OGG/Opus) using faster-whisper before forwarding to Scissari.

- **Whisper model:** `small`, cached at `~/.cache/huggingface/hub/models--Systran--faster-whisper-small`
- Loads at startup (~5s); log line: `Whisper model ready.`
- Transcription runs CPU/int8 — a few seconds per voice message
- Handler registered as `MessageHandler(filters.VOICE, handle_voice)`

### Pip install gotcha for this venv

`claude-agent-sdk-demos/.venv` contains **both `python3.10` and `python3.12` dirs**. The bot runs on 3.10. Plain `pip install` silently drops packages into 3.12 where they are invisible at runtime. Always use:

```bash
.venv/bin/pip install <pkg> --target .venv/lib/python3.10/site-packages
```

Verify with:
```bash
.venv/bin/python -c "import <pkg>; print('OK')"
```

## Voice output (TTS) — no API key required

Scissari speaks replies back as voice notes using **edge-tts** (Microsoft Edge Neural TTS, free, no API key).

- Voice: `en-US-AriaNeural` (female English, natural sounding)
- Install: `pip install edge-tts --target .venv/lib/python3.10/site-packages`
- The bot saves a `.mp3` via `edge_tts.Communicate(text, voice).save(path)` then sends via `reply_voice()`
- If TTS fails for any reason, the bot falls back to sending a text reply so the user always gets something

**Why edge-tts instead of OpenAI TTS**: OpenAI TTS requires an API key. The setup was switched to ChatGPT OAuth (no separate API key), so OpenAI TTS was replaced with edge-tts which requires no key.

## No-reply issue

If Scissari ignores messages, see `references/scissari-telegram-noreply.md` in the
`reliable-agent-messaging` skill. The fix (message prefix) is already in the bot.

If a message appears to "succeed" but no reply materializes, also check the local `8091` API and the `lettabot` logs before chasing Telegram delivery.
