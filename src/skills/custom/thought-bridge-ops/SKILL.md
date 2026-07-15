# thought-bridge-ops

Operations skill for the Scissari Live Thought Monitor — the WebSocket pipeline that streams Scissari's reasoning chunks to a browser terminal in real time.

## Architecture

```
lettabot (producer) → thought_bridge.py (:8766) → browser (ws://100.72.158.63:8766)
                                                 ↑
                             serve_monitor.py (:8899) serves the HTML over HTTP
```

> Port is **8766**, not 8765 — 8765 is the dashboard server on the same host.
> Lettabot's `~/lettabot/.env` sets `THOUGHT_BRIDGE_URL=ws://localhost:8766`.

- **Producer**: `thought-broadcaster.ts` singleton in lettabot; fires on `reasoning`, `tool_call`, `tool_result` stream events in `processMessage`, `sendToAgent`, and `streamToAgent`.
- **Bridge**: `thought_bridge.py` — Python asyncio WebSocket server; role-negotiated (first message `{"role":"producer"}` = producer, else consumer).
- **HTML monitor**: `monitor_thoughts_plan.html` — GoF-patterned black/white MSI-style terminal.
- **HTTP server**: `serve_monitor.py` — needed because `https://` pages can't open `ws://` (mixed content).

## Files

| File | Purpose |
|------|---------|
| `/home/adamsl/planner/a2a_communicating_agents/thought_bridge.py` | WebSocket fanout server (port 8766) |
| `/home/adamsl/planner/a2a_communicating_agents/serve_monitor.py` | HTTP server for HTML (port 8899) |
| `/home/adamsl/planner/a2a_communicating_agents/monitor_thoughts_plan.html` | Browser terminal UI |
| `/home/adamsl/lettabot/src/core/thought-broadcaster.ts` | TS singleton WebSocket producer |
| `/home/adamsl/planner/a2a_communicating_agents/logs/thought_bridge.log` | Bridge server log |
| `/home/adamsl/planner/a2a_communicating_agents/logs/monitor_http.log` | HTTP server log |
| `/home/adamsl/lettabot/lettabot-api.json` | Lettabot API key (for pipeline tests) |

## Starting the stack (systemd-managed — preferred)

Both processes run as systemd **user** units; don't nohup them while the units are enabled
(you'll get EADDRINUSE):

```bash
systemctl --user restart thought-bridge.service thought-bridge-monitor.service
systemctl --user status thought-bridge.service --no-pager -l | head -20  # "Bridge ready."
journalctl --user -u thought-bridge.service -n 20 --no-pager

# Restart lettabot if the producer needs to reconnect quickly
systemctl --user list-units | grep -q lettabot && systemctl --user restart lettabot.service || \
  { kill $(pgrep -f "dist/main.js" | head -1) 2>/dev/null; sleep 1; \
    nohup bash /home/adamsl/lettabot/start_scissari_bot.sh > /tmp/lettabot-new.log 2>&1 & }
```

Manual fallback (stop the units first): run `thought_bridge.py` and `serve_monitor.py`
with `/home/adamsl/ws-venv/bin/python3` (has `websockets`; the old
`receipt_scanning_tools/venv` path is broken).

## Checking status

```bash
ss -ltn | grep -E ':(8766|8899)\b'          # both must be listening
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8899/   # 200 = monitor up
systemctl --user is-active thought-bridge.service thought-bridge-monitor.service
grep "ThoughtBroadcaster" /tmp/lettabot-new.log | tail -1  # should say "Connected"
journalctl --user -u thought-bridge.service -n 3 --no-pager  # producers=1
```

## URLs

- **Live monitor (use this)**: `http://100.72.158.63:8899/monitor`
- **Demo mode only**: https://americansjewelry.com/monitor_thoughts_plan.html
  - HTTPS page can't open `ws://` (mixed content). Shows mock thoughts.
  - Append `?live` to force live mode if `wss://` bridge is set up.

## Pipeline test

```python
# Run from WSL to verify end-to-end
VENV=/home/adamsl/ws-venv/bin/python3
$VENV - <<'EOF'
import asyncio, json, threading, time, urllib.request

API_KEY = json.load(open('/home/adamsl/lettabot/lettabot-api.json'))['apiKey']

async def consume(received):
    import websockets
    async with websockets.connect('ws://100.72.158.63:8766', open_timeout=5) as ws:
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

### Dashboard shows "NEEDS ATTENTION — Connection refused" / units crash-looping
- **Cause**: the repo directory moved (2026-07-14: `/home/adamsl/a2a_communicating_agents` →
  `/home/adamsl/planner/a2a_communicating_agents`), so both units failed with
  `status=200/CHDIR` and restart forever. `systemctl --user status` shows a huge
  "restart counter" and `Changing to the requested working directory failed`.
- **Fix**: update `WorkingDirectory`/`ExecStart` in
  `~/.config/systemd/user/thought-bridge{,-monitor}.service`, then
  `systemctl --user daemon-reload && systemctl --user restart thought-bridge thought-bridge-monitor`.
- **Gotcha**: a copy restored from an old snapshot may hardcode `PORT = 8765` in
  `thought_bridge.py` (and `ws://…:8765` in `monitor_thoughts_plan.html`) — that collides
  with the dashboard. The bridge port must be **8766** everywhere.

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
