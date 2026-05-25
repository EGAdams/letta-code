---
name: maintaining-letta-dev-environment
description: Maintains the local Letta development setup across the main checkout, upstream worktree, self-hosted memfs, and the Windows Docker server. Use when syncing the worktree from the main checkout, rebuilding/running Letta locally, troubleshooting self-hosted memfs, enabling SSH on the Windows host, or preparing a safe Letta server upgrade without losing agents.
---

# Maintain Letta Dev Environment

## When to use
- The upstream worktree has drifted from the main checkout
- The worktree must behave like the main checkout before testing
- Local Letta must be rebuilt and run against a project directory
- `/memfs enable --selfhosted` fails on the Windows self-hosted server
- The Windows host needs SSH, firewall, or listening-port recon
- The Docker Letta server must be upgraded without losing agents

## Default workflow
1. Sync the worktree from the main checkout and rebuild it.
2. Run the correct local Letta binary against the target project directory.
3. If memfs fails, determine whether the problem is client code, repo URL construction, or server version.
4. If the server is Windows-hosted Docker, verify SSH/firewall state and inspect the container before changing it.
5. Before any server upgrade, confirm persistent Postgres storage and take a backup.

## Key commands

Sync main checkout into the upstream worktree:
```bash
/home/adamsl/letta-code/scripts/sync-upstream-worktree.sh
```

Run the main checkout locally:
```bash
/home/adamsl/letta-code/scripts/run-local-in-dir.sh /home/adamsl/rol_finances
```

Run the upstream worktree locally:
```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/rol_finances
```

Set up or verify upstream/worktree wiring:
```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/setup_upstream_worktree.sh \
  /home/adamsl/letta-code \
  letta-ai/letta-code \
  /home/adamsl/letta-code-upstream \
  sync-upstream
```

Verify or publish the sync worktree:
```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/test_and_sync_worktree.sh \
  /home/adamsl/letta-code-upstream \
  verify-only
```

## Memfs triage
- If `--selfhosted` is rejected outright, the running `letta.js` is too old.
- If clone fails with `repository .../state.git not found`, the self-hosted server is the blocker, not the port.
- Check `http://10.0.0.143:8283/openapi.json`. If the server is still around `0.16.x` and exposes no git paths, Git-backed memfs will not work yet.
- Use the `debugging-memfs-selfhosted` skill when the issue is clearly memfs-specific.

## Windows host
- Use the PowerShell recon steps in [references/windows-host-recon.md](references/windows-host-recon.md).
- Port `8283` being reachable is enough for the Letta API.
- SSH requires Windows OpenSSH Server on port `22`; it is separate from Letta itself.
- If shell access is unavailable, HTTP access to `http://10.0.0.143:8283/openapi.json` is still enough to confirm the running Letta server version.
- Current known state from 2026-03-15:
  - `10.0.0.143:8283` is reachable
  - the Windows firewall already allows `8283`
  - the server was upgraded from `0.16.3` to `0.16.6`
  - `0.16.6` still returns `501 Not Implemented` for `/v1/git/<agent-id>/state.git`
  - Git-backed memfs therefore still requires a newer server image
  - port `22` was not listening, so direct SSH access was not yet available

## Safe Docker upgrade rule
- Do not replace or remove the backing Postgres data volume before backup.
- Confirm the container mounts persistent Postgres storage first.
- Prefer inspecting the running container and compose settings before touching the image.
- Use `/home/adamsl/letta-code/scripts/windows-upgrade-letta-docker.ps1` on the Windows host to inspect, back up, and recreate the Letta container with the same mounts, env vars, ports, and restart policy.
- Prefer a pinned modern image tag such as `letta/letta:0.18.4` over `latest` when `latest` resolves to an older release.
