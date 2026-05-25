---
name: building-letta-server-from-source
description: Builds and upgrades a self-hosted Letta server from source in WSL using Docker while preserving existing agents. Use when the published Docker image is too old for required features such as git-backed memfs, or when the Windows host runs Docker through WSL and the server must be rebuilt from the latest source.
---

# Build Letta Server From Source

## When to use
- The Docker image registry only provides an older Letta version
- The running server returns `501 Not Implemented` for `/v1/git/<agent-id>/state.git`
- Git-backed memfs is required and the published image is too old
- Docker and Letta are both run inside WSL on the Windows machine

## Goal
- Build a newer Letta server image from the official source repo
- Recreate the running container without losing agents
- Preserve the existing Postgres data mount and keep the old container as rollback

## Required assumptions
- The current Letta server is running in Docker
- Agent data lives in Postgres on a persistent Docker bind mount or volume
- Work is done inside WSL, not native PowerShell
- The official source repo is `https://github.com/letta-ai/letta.git`

## Safety rules
1. Inspect the running container before changing anything.
2. Refuse to proceed if there is no Postgres mount at `/var/lib/postgresql/data`.
3. Save `docker inspect` and recent logs before the upgrade.
4. Rename the old container instead of deleting it.
5. Reuse the same mounts, ports, env vars, restart policy, and command.

## Official references
- Source install guide: https://docs.letta.com/guides/server/source/
- Pip/server notes about Postgres migrations: https://docs.letta.com/guides/server/pip/
- Official source repo: https://github.com/letta-ai/letta

## Workflow
1. In WSL, clone `letta-ai/letta` if it is not already present.
2. Inspect the current container on port `8283` and confirm persistent Postgres storage.
3. Build a Docker image from the checked out source.
4. Stop and rename the old container.
5. Start a new container from the locally built image using the same runtime settings.
6. Verify `http://localhost:8283/openapi.json`.
7. Retry `/memfs enable --selfhosted http://10.0.0.143:8283`.

## Key commands

Clone source:
```bash
git clone https://github.com/letta-ai/letta.git
```

Sync Python environment if running from source directly:
```bash
cd letta
uv sync --all-extras
uv run letta server
```

Build Docker image from source:
```bash
cd letta
docker build -t letta-from-source:local .
```

Check server version after upgrade:
```bash
curl http://localhost:8283/openapi.json
```

## What to inspect first
- `docker ps`
- `docker inspect <container>`
- `docker logs --tail 200 <container>`
- container mounts, especially `/var/lib/postgresql/data`
- current published port `8283`

## Expected decision points
- If the current container has no persistent Postgres mount, stop and ask for backup instructions before upgrade.
- If the official source Docker build fails, inspect the repo’s `Dockerfile`, `compose.yaml`, and `pyproject.toml`.
- If the new server still reports an old version, the wrong image was launched.

## Output
Report:
1. Source commit or branch used
2. Docker image tag built
3. Old container name and backup name
4. Postgres mount preserved
5. New server version from `openapi.json`
6. Whether git-backed memfs now works
