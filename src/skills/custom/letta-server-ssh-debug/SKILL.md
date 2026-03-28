---
name: letta-server-ssh-debug
description: How to SSH into the Windows 10 machine at 10.0.0.143 that runs the Letta server in Docker, inspect container state, clear stuck approval locks, and debug agent issues from the command line. Use when the agent is stuck, the Letta server needs inspection, Docker containers need restarting, or a new .ps1 setup script is needed for that machine.
---

# Letta Server SSH Debug

## Environment

| Item | Value |
|------|-------|
| Remote machine | Windows 10 at `10.0.0.143` |
| SSH user | `NewUser` |
| SSH key | `~/.ssh/id_ed25519` |
| Letta container | `letta-server` (port 8283) |
| Redis container | `letta-redis` (port 6379) |
| Postgres container | `letta-postgres` (port 5432) |
| Memfs container | `letta-memfs` (port 8285) |
| Letta version | 0.16.3 |
| Active agent | Quinn — `agent-fcbd78e5-abcd-459e-852e-921d4946223e` |

SSH works with key auth — no password needed:
```bash
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "<command>"
```

## Docker Commands (run via SSH)

```bash
# List running containers
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker ps"

# Tail Letta server logs
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker logs letta-server --tail 50"

# Follow logs live
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker logs -f letta-server"

# Restart Letta server (clears stuck approval state)
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker restart letta-server"

# Exec into the container
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker exec -it letta-server bash"
```

## Diagnosing a Stuck Approval

When the user gets:
```
⚠ CONFLICT: Cannot send a new message: The agent is waiting for approval on a tool call.
```

### Step 1 — Check agent state via API (from WSL, no SSH needed)
```bash
AGENT="agent-fcbd78e5-abcd-459e-852e-921d4946223e"
curl -s "http://10.0.0.143:8283/v1/agents/$AGENT" | python3 -c "
import sys,json; a=json.load(sys.stdin)
print('agent_state:', a.get('agent_state'))
print('in_context_message_ids:', a.get('in_context_message_ids', [])[-5:])
"
```

### Step 2 — Check conversations for pending approval message
```bash
AGENT="agent-fcbd78e5-abcd-459e-852e-921d4946223e"
# List conversations
curl -s "http://10.0.0.143:8283/v1/conversations/?agent_id=$AGENT&limit=10" | \
  python3 -c "import sys,json; [print(c['id'], c.get('created_at','')[:19]) for c in json.load(sys.stdin)]"

# Then for each conv-id, check messages
CONV="<conv-id-from-above>"
curl -s "http://10.0.0.143:8283/v1/conversations/$CONV/messages?limit=10&order=desc" | \
  python3 -c "
import sys,json
for m in json.load(sys.stdin):
    tc = m.get('tool_calls') or ([m.get('tool_call')] if m.get('tool_call') else [])
    print(m.get('message_type'), [t.get('tool_call_id') for t in tc if t])
"
```

### Step 3 — Cancel stuck run via API
```bash
AGENT="agent-fcbd78e5-abcd-459e-852e-921d4946223e"
# Cancel using agent ID (works because Letta accepts agent_id as conversation_id for default conv)
curl -s -X POST "http://10.0.0.143:8283/v1/conversations/$AGENT/cancel" \
  -H "Content-Type: application/json" -d '{}'

# Or cancel a specific conversation
curl -s -X POST "http://10.0.0.143:8283/v1/conversations/$CONV/cancel" \
  -H "Content-Type: application/json" -d '{}'
```

### Step 4 — Nuclear option: restart the container
```bash
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker restart letta-server"
# Wait ~10s for it to come back healthy
ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "docker ps"
```

## Setting Up SSH on a New Windows 10 Machine

If SSH isn't running on the target machine, use these scripts (stored in `/home/adamsl/letta-code/`):

### Scripts

| Script | Purpose |
|--------|---------|
| `recon.sh` | Check connectivity, open ports, existing keys |
| `install_openssh2.ps1` | Download and install OpenSSH Server from GitHub (no Windows Update needed) |
| `fix_ssh_auth.ps1` | Write authorized_keys for both admin and regular user paths |
| `fix_ssh_config.ps1` | Uncomment `PubkeyAuthentication yes` and write `administrators_authorized_keys` |

### Workflow

1. Run `./recon.sh` to check what ports are open
2. If port 22 is closed, copy `install_openssh2.ps1` to the Windows machine and run as Administrator:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   .\install_openssh2.ps1
   ```
3. If key auth fails, copy and run `fix_ssh_config.ps1` as Administrator
4. Test: `ssh -i ~/.ssh/id_ed25519 NewUser@10.0.0.143 "whoami"`

### Key auth gotcha on Windows

Windows OpenSSH uses **two different authorized_keys locations** depending on group membership:
- **Administrators group** → `C:\ProgramData\ssh\administrators_authorized_keys`
  - Permissions: `SYSTEM:F` + `Administrators:F` only (no inheritance)
- **Standard users** → `C:\Users\<name>\.ssh\authorized_keys`
  - Permissions: `<username>:F` + `SYSTEM:F` only (no inheritance)
- `PubkeyAuthentication yes` must be **uncommented** in `C:\ProgramData\ssh\sshd_config`

Public key (from `~/.ssh/id_ed25519.pub`):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJu4jIb5347YGP4FwD9xaFEERPdjBoNBUYJdiCzh3a5G adamsl@DESKTOP-2OBSQMC
```

## Letta API Quick Reference (Letta 0.16.3)

```bash
BASE="http://10.0.0.143:8283"

# List agents
curl -s "$BASE/v1/agents/" | python3 -c "import sys,json; [print(a['id'], a['name']) for a in json.load(sys.stdin)]"

# List conversations for an agent
curl -s "$BASE/v1/conversations/?agent_id=$AGENT" | python3 -c "import sys,json; [print(c['id']) for c in json.load(sys.stdin)]"

# Send a test message (non-streaming)
curl -s -X POST "$BASE/v1/conversations/$CONV/messages" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hello"}],"streaming":false}'

# Cancel a conversation run
curl -s -X POST "$BASE/v1/conversations/$CONV/cancel" -H "Content-Type: application/json" -d '{}'
```
