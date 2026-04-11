---
name: operating-letta-across-machines
description: Operates Letta workflows across multiple machines using Tailscale, SSH, SCP, and remote Ubuntu/WSL shells. Use when a task involves another machine, remote file access, cross-machine memfs sync, Tailscale reachability, or when the user wants files inspected, copied, or edited on a different computer.
---

# Operating Letta Across Machines

## Overview

Use this skill when Letta work spans more than one machine, especially for Tailscale-connected Windows + WSL/Ubuntu setups.

Prefer the Linux/WSL target when the files or repos live in Ubuntu.

## Core rules

1. **Prefer `scp` over asking the user to copy/paste files manually** when SSH access is available.
2. **Target the Ubuntu/WSL machine**, not the Windows side, when the path is Linux-like, such as `/home/adamsl/...`.
3. **Check Tailscale reachability before debugging SSH auth**.
4. **Expect non-interactive SSH shells to miss PATH setup** for `node`, `bun`, `nvm`, or similar tools.
5. When working on Letta memfs remotely, verify both:
   - the Letta/memfs CLI view
   - the underlying git repo state

## Quick remote workflow

### 1. Identify the right host
- If the user gives both Windows and Ubuntu/WSL nodes, use the Ubuntu/WSL node for Linux paths.
- If the Ubuntu node is offline in Tailscale, stop there first and diagnose that.

### 2. Check Tailscale status
Run checks like:

```bash
tailscale status
tailscale ping <host>
```

If the target is offline or ping times out, fix that before trying deeper SSH steps.

### 3. Check SSH reachability
Use SSH with safe host-key acceptance when needed:

```bash
ssh -o StrictHostKeyChecking=accept-new user@host
scp -o StrictHostKeyChecking=accept-new localfile user@host:/path/
```

If SSH times out, treat it as connectivity or target-offline issue.
If SSH says `Permission denied`, treat it as auth/key issue.

If SSH says `Host key verification failed`, accept the host key first and retry before doing deeper auth work.

### 4. Inspect remote shell environment
Non-interactive shells may not load the same PATH as interactive login shells.

Check:

```bash
echo $PATH
which node
which bun
node --version
bun --version
```

If tools are missing but installed under the user home, inspect:
- `~/.bashrc`
- `~/.profile`
- `~/.bash_profile`

Typical fixes include prepending:
- `~/.bun/bin`
- `~/.nvm/versions/node/<version>/bin`

Example workaround used successfully on a remote Ubuntu machine:

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | tail -n 1)/bin:$PATH"
```

## Remote memfs workflow

When verifying agent memory on another machine:

1. Go to the relevant working directory if needed.
2. Run Letta memfs commands from shell form:

```bash
letta memfs status --agent <agent-id>
letta memfs pull --agent <agent-id>
```

3. Also inspect git directly:

```bash
git -C ~/.letta/agents/<agent-id>/memory status --short
git -C ~/.letta/agents/<agent-id>/memory remote -v
```

4. If the remote machine uses the wrong memfs remote, correct the remote config only after backing up the local memory dir.

## Common repair sequence for SSH auth between Linux machines

If machine A must SSH to machine B and gets `Permission denied (publickey,password)`:

1. Read machine A's public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

2. Append that key to machine B's `~/.ssh/authorized_keys`
3. Retry SSH from machine A to machine B

This exact pattern was needed to let mom's Ubuntu machine reach the Scissari memfs host.

## References

Read these files when needed:

- `references/remote-checklist.md`
- `references/scissari-memfs-notes.md`
- `references/scissari-telegram-bot.md` — Scissari's Telegram bot (`@scissaribot`), how to start it, and the wrong-bot mistake to avoid

Read the Scissari notes when the task is specifically about Scissari, mom's machine, rosemary/desktop hosts, or the shared memfs remote.
Read the Telegram bot notes when the user mentions "lettabot", "scissaribot", or Telegram communication with Scissari.
