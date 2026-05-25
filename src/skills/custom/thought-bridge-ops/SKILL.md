# thought-bridge-ops

Operations skill for the Scissari Live Thought Monitor — the WebSocket pipeline that streams Scissari's reasoning chunks to a browser terminal in real time.

## Architecture

```
lettabot (producer) → thought_bridge.py (:8765) → browser (ws://100.72.158.63:8765)
                                                 ↑
                             serve_monitor.py (:8899) serves the HTML over HTTP
```

- **Producer**: `thought-broadcaster.ts` singleton in lettabot; fires on `reasoning`, `tool_call`, `tool_result` stream events in `processMessage`, `sendToAgent`, and `streamToAgent`.
- **Bridge**: `thought_bridge.py` — Python asyncio WebSocket server; role-negotiated (first message `{"role":"producer"}` = producer, else consumer).
- **HTML monitor**: `monitor_thoughts_plan.html` — GoF-patterned black/white MSI-style terminal.
- **HTTP server**: `serve_monitor.py` — needed because `https://` pages can't open `ws://` (mixed content).

## Files

| File | Purpose |
|------|---------|
| `/home/adamsl/planner/a2a_communicating_agents/thought_bridge.py` | WebSocket fanout server (port 8765) |
| `/home/adamsl/planner/a2a_communicating_agents/serve_monitor.py` | HTTP server for HTML (port 8899) |
| `/home/adamsl/planner/a2a_communicating_agents/monitor_thoughts_plan.html` | Browser terminal UI |
| `/home/adamsl/lettabot/src/core/thought-broadcaster.ts` | TS singleton WebSocket producer |
| `/home/adamsl/planner/a2a_communicating_agents/logs/thought_bridge.log` | Bridge server log |
| `/home/adamsl/planner/a2a_communicating_agents/logs/monitor_http.log` | HTTP server log |
| `/home/adamsl/lettabot/lettabot-api.json` | Lettabot API key (for pipeline tests) |

## Starting the stack

```bash
VENV=/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/venv/bin/python3
mkdir -p /home/adamsl/planner/a2a_communicating_agents/logs

# 1. Bridge
nohup $VENV /home/adamsl/planner/a2a_communicating_agents/thought_bridge.py \
  > /home/adamsl/planner/a2a_communicating_agents/logs/thought_bridge.log 2>&1 &

# 2. HTTP monitor server
nohup $VENV /home/adamsl/planner/a2a_communicating_agents/serve_monitor.py \
  > /home/adamsl/planner/a2a_communicating_agents/logs/monitor_http.log 2>&1 &

# 3. Restart lettabot (if not running or after rebuild)
kill $(pgrep -f "dist/main.js" | head -1) 2>/dev/null; sleep 1
nohup bash /home/adamsl/lettabot/start_scissari_bot.sh > /tmp/lettabot-new.log 2>&1 &

# 4. Confirm producer connected
until grep -q "Connected to bridge" /tmp/lettabot-new.log; do sleep 2; done
tail -3 /home/adamsl/planner/a2a_communicating_agents/logs/thought_bridge.log
```

## Checking status

```bash
pgrep -f "thought_bridge.py" && echo "bridge OK" || echo "bridge DOWN"
pgrep -f "serve_monitor.py"  && echo "http OK"   || echo "http DOWN"
pgrep -f "dist/main.js"      && echo "lettabot OK" || echo "lettabot DOWN"
grep "ThoughtBroadcaster" /tmp/lettabot-new.log | tail -1  # should say "Connected"
tail -3 /home/adamsl/planner/a2a_communicating_agents/logs/thought_bridge.log  # producers=1
```

## URLs

- **Live monitor (use this)**: `http://100.72.158.63:8899/monitor`
- **Demo mode only**: https://americansjewelry.com/monitor_thoughts_plan.html
  - HTTPS page can't open `ws://` (mixed content). Shows mock thoughts.
  - Append `?live` to force live mode if `wss://` bridge is set up.

## Pipeline test

```python
# Run from WSL to verify end-to-end
VENV=/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/venv/bin/python3
$VENV - <<'EOF'
import asyncio, json, threading, time, urllib.request

API_KEY = json.load(open('/home/adamsl/lettabot/lettabot-api.json'))['apiKey']

async def consume(received):
    import websockets
    async with websockets.connect('ws://100.72.158.63:8765', open_timeout=5) as ws:
        await asyncio.wait_for(ws.recv(), timeout=3)  # welcome
        try:
            while True:
                data = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                received.append(data)
                print(f'[{data.get("kind")}] {data.get("text","")[:80]}')
        except asyncio.TimeoutError:
            pass

def chat():
    time.sleep(1.5)
    body = json.dumps({"message": "Run bash: echo hello && date"}).encode()
    req = urllib.request.Request('http://127.0.0.1:8091/api/v1/chat', data=body,
        headers={'Content-Type': 'application/json', 'x-api-key': API_KEY}, method='POST')
    with urllib.request.urlopen(req, timeout=45) as r:
        print(json.loads(r.read()).get('response','')[:200])

received = []
t = threading.Thread(target=chat, daemon=True)
t.start()
asyncio.run(consume(received))
t.join(timeout=3)
print(f'Thoughts: {len(received)}  PASS' if received else 'FAIL — no thoughts')
EOF
```

## Troubleshooting

### Page stuck on "CONNECTING..." / Chrome TypeError `classList` of null
- **Cause**: `id="progress-fill indeterminate"` (space in ID) → querySelector returns null → crash in setStatus before WS starts.
- **Check**: Chrome DevTools → Console for `TypeError: Cannot read properties of null (reading 'classList')`.
- **Fix**: ensure `<div id="progress-fill" class="indeterminate">` (separate id and class attributes).

### 0 thoughts despite Scissari responding
- **Cause A**: ThoughtBroadcaster not connected — check `grep "Connected to bridge" /tmp/lettabot-new.log`.
- **Cause B**: Message went through `sendToAgent()` (API path) but broadcaster not wired there. Verify `[sendToAgent] type=reasoning` appears in log AND bridge shows fanout. Fixed in `sendToAgent` and `streamToAgent` in bot.ts.
- **Cause C**: Scissari returned a cached/replayed response (no new reasoning generated). Wait a few seconds and try again with a tool-forcing message.

### Node.js 22 WebSocket reconnect never fires
- Node.js 22 built-in WebSocket does NOT fire `close` on ECONNREFUSED — only `error`.
- Reconnect must be scheduled in the `error` handler (already fixed in thought-broadcaster.ts).

### Mixed content in browser console
- `ws://` blocked from `https://` page. Use `http://100.72.158.63:8899/monitor` instead.
- For WSS support: `sudo tailscale cert desktop-2obsqmc-24.tailb8fc54.ts.net` then add TLS to thought_bridge.py.

### Producer not reconnecting after lettabot restart
- Broadcaster has exponential backoff: 1s, 2s, 5s, 10s, 30s.
- After 5+ failures it retries every 30s. Start bridge BEFORE lettabot to avoid long wait.
- Force reconnect: restart lettabot.
