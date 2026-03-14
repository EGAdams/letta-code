---
name: agent-manager
description: List/search agents on a self-hosted Letta server via the /v1/agents API. Use when you need to discover agents, filter by tags, or include memory blocks.
---

# Agent Manager

## When to use
- You need to list agents on the current Letta server.
- You want to search by name/query or filter by tags.
- You want to include memory blocks for inspection.

## Quick start (list all agents)
```bash
python3 /home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py
```

## Search by name or query
```bash
python3 /home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py --name "Scissari"
python3 /home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py --query "finance"
```

## Filter by tags
```bash
python3 /home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py --tags "origin:letta-code,production"
```

## Include memory blocks (JSON only)
```bash
python3 /home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py --include-blocks --json
```

## Notes
- Base URL defaults to `LETTA_BASE_URL` or falls back to `http://10.0.0.143:8283`.
- If the server requires auth, set `LETTA_API_KEY` or pass `--api-key`.
