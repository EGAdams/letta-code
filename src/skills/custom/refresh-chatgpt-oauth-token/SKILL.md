---
name: refresh-chatgpt-oauth-token
description: Refresh the ChatGPT OAuth token in the Letta server DB using the local Codex CLI auth.json, and switch an agent's model. Use when Scissari (or any agent on chatgpt-plus-pro) gets llm_api_error or llm_authentication errors. Also covers changing an agent's model to any gpt-5.x-codex variant.
---

# Refresh ChatGPT OAuth Token / Switch Agent Model

## When to use

- Letta logs show `llm_api_error` or `llm_authentication` / `UNAUTHENTICATED: Failed to obtain valid ChatGPT OAuth credentials`
- Agent stops responding with no content, just error result
- You want to switch an agent to a different `chatgpt-plus-pro` model

## Architecture

```
~/.codex/auth.json          — Codex CLI stores fresh OAuth tokens here
                              (refreshed automatically when you use Codex CLI)

letta-server DB             — provider row: name='chatgpt-plus-pro'
  └── api_key_enc (JSON)    — must contain: access_token, refresh_token,
                              account_id, expires_at (Unix seconds)
                              The server auto-refreshes using refresh_token
                              before each call (5-min buffer).
```

The Letta server is at `http://100.80.49.10:8283` (direct to letta-server). The old letta-bridge nginx proxy on `18283` is down/retired as of 2026-05-29 — use `8283`.  
SSH to Docker host: `ssh 100.80.49.10`  
Docker command prefix: `ssh 100.80.49.10 "docker exec letta-server python3 -c \"...\""  `

## Step 1 — Refresh the token in the Letta server DB

```bash
# Build full credentials JSON from local Codex CLI auth, base64-encode for safe shell transfer
python3 -c "
import json, base64

with open('/home/adamsl/.codex/auth.json') as f:
    d = json.load(f)
tokens = d['tokens']

# Decode JWT to get expires_at
parts = tokens['access_token'].split('.')
payload_b64 = parts[1] + '==' * (4 - len(parts[1]) % 4)
payload = json.loads(base64.b64decode(payload_b64))

creds = {
    'access_token': tokens['access_token'],
    'refresh_token': tokens['refresh_token'],
    'account_id': tokens['account_id'],
    'expires_at': payload['exp']
}
print(base64.b64encode(json.dumps(creds).encode()).decode())
" > /tmp/chatgpt_token_b64.txt

B64=$(cat /tmp/chatgpt_token_b64.txt | tr -d '\n')

ssh 100.80.49.10 "echo '$B64' | docker exec -i letta-server python3 -c \"
import asyncio, sys, json, base64
sys.path.insert(0, '/app')
from letta.server.db import db_registry
from letta.orm.provider import Provider
from sqlalchemy import select
from datetime import datetime, timezone

b64 = sys.stdin.read().strip()
new_enc = base64.b64decode(b64).decode()
parsed = json.loads(new_enc)
print('Token expires_at:', parsed['expires_at'], '| account_id:', parsed['account_id'])

async def update():
    async with db_registry.async_session() as session:
        result = await session.execute(select(Provider).where(Provider.name == 'chatgpt-plus-pro'))
        p = result.scalar_one()
        p.api_key_enc = new_enc
        p.last_synced = datetime.now(timezone.utc)
        await session.commit()
        print('Done.')

asyncio.run(update())
\""
```

## Step 2 — Verify it works

```bash
curl -s -X POST http://100.80.49.10:8283/v1/agents/<AGENT_ID>/messages \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hi in 3 words"}],"stream":false}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d.get('messages', []):
    if m.get('message_type') == 'assistant_message':
        print('OK:', m['content'][:100])
if 'error' in d:
    print('ERROR:', d)
"
```

## Switch an agent's model

Available `chatgpt-plus-pro` models (as of 2026-05-23):
- `gpt-5.4` / `gpt-5.4-pro` / `gpt-5.4-fast` / `gpt-5.4-mini`
- `gpt-5.3-codex` / `gpt-5.3-codex-spark`  ← Scissari's preferred model
- `gpt-5.2` / `gpt-5.2-codex`
- `gpt-5.1-codex` / `gpt-5.1-codex-mini` / `gpt-5.1-codex-max`
- `gpt-4o` / `o1` / `o3` / `o4-mini`

```bash
MODEL="gpt-5.3-codex"
AGENT_ID="agent-5955b0c2-7922-4ffe-9e43-b116053b80fa"  # Scissari

curl -s -X PATCH http://100.80.49.10:8283/v1/agents/$AGENT_ID \
  -H "Content-Type: application/json" \
  -d "{
    \"llm_config\": {
      \"model\": \"$MODEL\",
      \"model_endpoint_type\": \"chatgpt_oauth\",
      \"model_endpoint\": \"https://chatgpt.com/backend-api/codex/responses\",
      \"provider_name\": \"chatgpt-plus-pro\",
      \"provider_category\": \"byok\",
      \"context_window\": 272000,
      \"handle\": \"chatgpt-plus-pro/$MODEL\",
      \"temperature\": 0.7,
      \"max_tokens\": 128000,
      \"enable_reasoner\": true,
      \"reasoning_effort\": \"medium\",
      \"max_reasoning_tokens\": 0,
      \"put_inner_thoughts_in_kwargs\": false,
      \"parallel_tool_calls\": true,
      \"strict\": true
    }
  }" | python3 -c "
import sys, json
d = json.load(sys.stdin)
cfg = d.get('llm_config', {})
print('model:', cfg.get('model'))
print('handle:', cfg.get('handle'))
if 'error' in d: print('ERROR:', d)
"
```

## Key agent IDs

| Agent | ID |
|---|---|
| Scissari (LettaBot) | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |

## Notes

- The Codex CLI (`/usr/local/bin/codex`) automatically refreshes `~/.codex/auth.json` tokens. If the access_token in that file is also expired, run Codex CLI briefly to trigger a refresh before running Step 1.
- After updating the DB, no restart of letta-server is needed — it reads credentials fresh per call.
- lettabot reads `baseUrl` from `/home/adamsl/lettabot/lettabot.yaml`. **Updated 2026-05-29:** the live letta-server is reachable directly on `100.80.49.10:8283` (verified HTTP 200, ADE-confirmed). The `letta-bridge` nginx proxy on `18283` is down/retired — `18283` refuses connections. Use `8283`. If you find a `lettabot.yaml` still pointing at `18283`, update it. (The old guidance that `8283` was "an orphan container, do NOT use" no longer holds — the infrastructure changed.)
