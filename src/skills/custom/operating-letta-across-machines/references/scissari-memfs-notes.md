# Scissari Memfs Notes

## Agent

- Scissari agent id: `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa`

## Intended shared memfs remote

```text
ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/scissari-memory.git
```

## Local memory path

```text
~/.letta/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/memory
```

## Important known issue from this session

Mom's Ubuntu machine (`rosemary46-24`) was still pointed at an older HTTP memfs remote and had local untracked memory content.

The main blocker to finishing sync migration was:

```bash
ssh adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net echo ok
```

failing **from the remote Ubuntu machine itself** with publickey auth errors.

That blocker was later resolved by appending `rosemary46-24`'s `~/.ssh/id_ed25519.pub` key to `desktop-2obsqmc-24`'s `~/.ssh/authorized_keys`.

After that, Scissari memfs on `rosemary46-24` was migrated cleanly to the shared SSH remote and verified clean.

## Scissari project context

Scissari is being prepared to take over ROL Finances planning, including:
- finance workflow / report planning
- agent creation / coordination responsibility
- memory-based handoff for the project

## Known useful conversation

- `conv-5e450cce-9f6b-47d1-989e-efbbbef629e8`