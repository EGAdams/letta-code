---
name: connecting-llm-oauth
description: Diagnoses and fixes broken OAuth connections for OpenAI (ChatGPT Plus/Pro) in Letta agents. Use when agents can't connect to OpenAI LLMs, when switching from API key to OAuth, when OPENAI_API_KEY needs to be removed, or when /connect chatgpt stops working. Covers token refresh, ~/.codex/auth.json fast path, and provider registration on the Letta server.
---

# Connecting LLM via OAuth

Letta agents connect to OpenAI via **ChatGPT OAuth** (using your Plus/Pro subscription) — NOT the pay-per-use API key.

## Architecture

- `/connect chatgpt` or `/connect codex` → OAuth (ChatGPT Plus/Pro)
- `/connect openai` → API key (BYOK, pay-per-use — avoid)

The OAuth provider name on the Letta server is `chatgpt-plus-pro` (type: `chatgpt_oauth`).

## Diagnosing broken OAuth

### 1. Check for stray API key in environment
```bash
env | grep OPENAI_API_KEY
```
If set, it doesn't block OAuth directly (letta-code ignores it), but it wastes money if other tools pick it up. Remove it from `~/.bashrc`.

### 2. Check OAuth tokens
```bash
cat ~/.codex/auth.json
```
Valid tokens have `"auth_mode": "chatgpt"` and a recent `last_refresh`. If `OPENAI_API_KEY` is `null`, the token was issued correctly.

### 3. Check stale oauthState in settings.json
A stale `oauthState` block in `~/.letta/settings.json` means a previous `/connect chatgpt` attempt didn't complete. Remove it:
```json
// Remove the "oauthState": { ... } block from ~/.letta/settings.json
```

### 4. Check whether the provider is registered on the Letta server
```bash
curl -s http://<LETTA_BASE_URL>/v1/providers | python3 -m json.tool
```
Look for `"provider_type": "chatgpt_oauth"` and `"provider_name": "chatgpt-plus-pro"`.

## Fixing broken OAuth

### Step 1 — Remove OPENAI_API_KEY from ~/.bashrc
Edit `~/.bashrc` and comment out or delete:
```bash
# export OPENAI_API_KEY='sk-proj-...'  # removed — using ChatGPT OAuth instead
```
Then reload: `source ~/.bashrc`

### Step 2 — Re-register the OAuth provider on the Letta server
Start letta-code and run:
```
/connect chatgpt
```
**Fast path:** If `~/.codex/auth.json` exists with valid tokens, it skips the browser flow entirely and POSTs the tokens directly to the Letta server's `/v1/providers` endpoint.

### Step 3 — Select a ChatGPT model
```
/model
```
Select a model under the `chatgpt-plus-pro` provider (e.g. `gpt-4o`).

## Token expiry

The `id_token` from ChatGPT expires in ~10 days. The Letta server handles refresh automatically (type `chatgpt_oauth`). If the token is expired and refresh fails, re-run `/connect chatgpt` — it will reload `~/.codex/auth.json` if Codex refreshed it, or trigger a new browser OAuth flow.

## Gemini

Gemini does not support OAuth in letta-code — it requires a direct API key via `/connect gemini <api_key>`. `GEMINI_API_KEY` / `GOOGLE_API_KEY` env vars are not read by letta-code; the key must be registered on the Letta server via the connect command.
