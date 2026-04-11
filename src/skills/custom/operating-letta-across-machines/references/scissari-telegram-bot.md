# Scissari Telegram Bot

## What it is

A Python bot (`@scissaribot`) that bridges Telegram messages to the Scissari Letta agent
via the Letta REST API.

## Key facts

| Item | Value |
|------|-------|
| Telegram bot | `@scissaribot` |
| Token env var | `TELEGRAM_TOKEN` in `~/.letta/.env` |
| Scissari agent ID | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |
| Letta API URL | `http://10.0.0.143:8283` |
| Bot script | `/home/adamsl/codex_test_agent/claude-agent-sdk-demos/telegram_integration/letta_telegram_bot.py` |
| Python venv | `/home/adamsl/codex_test_agent/claude-agent-sdk-demos/.venv` |
| Log file | `/tmp/scissari-telegram.log` |

## Start command

```bash
cd /home/adamsl/codex_test_agent/claude-agent-sdk-demos
nohup .venv/bin/python telegram_integration/letta_telegram_bot.py >> /tmp/scissari-telegram.log 2>&1 &
```

## Check if running

```bash
ps aux | grep letta_telegram_bot | grep -v grep
tail -20 /tmp/scissari-telegram.log
```

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
