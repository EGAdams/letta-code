# Steps for executing the Start button

Use these steps to make sure the dashboard "Start" button launches agents in the correct environment.

## 1) Build backend after any launch logic changes

```bash
cd /home/adamsl/planner/dashboard
npm run build:backend
```

## 2) Restart the dashboard backend process

Use your normal start/restart method for the dashboard backend (the process that serves `http://localhost:3030`).

## 3) Verify dashboard is reachable

Open:

- `http://localhost:3030/`

## 4) Click Start on the target agent row

In **Managed Agents**, click **Start** for the desired agent (for example `orchestrator-agent`).

## 5) Confirm launch result in terminal panel

Expected success indicators:

- startup logs appear
- no immediate Python import errors
- row status stays **Running**

Failure indicator to watch for:

- `ModuleNotFoundError: No module named ...`

If that appears, the launch command/venv mapping is still wrong for that agent.

## 6) API checks (optional, fast validation)

```bash
curl -s http://127.0.0.1:3030/api/servers
curl -s -X POST "http://127.0.0.1:3030/api/servers/orchestrator-agent?action=start"
curl -s http://127.0.0.1:3030/api/logs/orchestrator-agent
```

## Current implementation note

The backend now supports centralized agent command overrides so Start-button launches can be pinned to known-good `command` and `cwd` per agent.