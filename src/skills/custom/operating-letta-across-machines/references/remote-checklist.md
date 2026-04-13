# Remote Machine Checklist

## Tailscale first

1. `tailscale status`
2. `tailscale ping <host>`
3. If offline or timing out, stop and fix reachability first.

## Pick the correct host

- Use the Ubuntu/WSL host for Linux paths like `/home/adamsl/...`
- Do not target the Windows host when the file actually lives in WSL

## SSH / SCP checks

### Connectivity

```bash
ssh -o StrictHostKeyChecking=accept-new user@host
```

- timeout => connectivity / target offline / SSH daemon issue
- permission denied => auth/key issue
- host key verification failed => accept/update known host entry

Useful pattern:

```bash
ssh -o StrictHostKeyChecking=accept-new user@host
```

### Prefer SCP to manual copy/paste

```bash
scp -o StrictHostKeyChecking=accept-new file user@host:/path/
```

Use `scp` whenever remote file transfer is available.

## Remote environment checks

For non-interactive SSH sessions:

```bash
echo $PATH
which node
which bun
node --version
bun --version
```

If missing, inspect shell startup files and prepend user-installed tool paths.

Known working workaround for remote non-interactive shells:

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | tail -n 1)/bin:$PATH"
```

## Remote Letta/memfs checks

```bash
letta memfs status --agent <agent-id>
letta memfs pull --agent <agent-id>
git -C ~/.letta/agents/<agent-id>/memory status --short
git -C ~/.letta/agents/<agent-id>/memory remote -v
```

## Safe repair pattern for memfs

1. Back up the memory directory before changing remotes.
2. Inspect local untracked or dirty files.
3. Confirm SSH auth to the intended remote host works from the remote machine itself.
4. Only then switch remotes or reset to remote state.

## If one Linux machine must SSH to another Linux machine

If host A cannot SSH to host B with publickey auth:

1. On host A, print the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

2. On host B, append it to:

```bash
~/.ssh/authorized_keys
```

3. Retry from host A.