---
name: agent-bootstrap
description: Create/refresh all ROL Finances agents on the current Letta server and overwrite AGENT_REGISTRY with current server IDs.
---

# Agent Bootstrap (ROL Finances)

Use this skill to ensure all agents in `AGENT_REGISTRY.json` exist on the **current Letta server**.

## What it does
- Resolves the active Letta server (from `LETTA_BASE_URL` or `~/.letta/settings.json`).
- Creates any missing agents by running the corresponding `create_*.py` scripts.
- Overwrites `external_agents/AGENT_REGISTRY.json` and `.md` with the new server IDs.

## Usage
```bash
python3 /home/adamsl/letta-code/src/skills/custom/agent-bootstrap/scripts/bootstrap_agents.py
```

## Notes
- Requires `letta-client` in `/home/adamsl/rol_finances/.venv`.
- Uses the ROL Finances agent creation scripts under `/home/adamsl/rol_finances/external_agents/`.
