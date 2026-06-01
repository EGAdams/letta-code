# SSH Access — DESKTOP-SHDBATI

This box is a **Windows 10 Home** host (`DESKTOP-SHDBATI`) running **WSL Ubuntu 24.04**.
There are **two separate SSH targets**, each with its own user. Almost everything the team
works on — the Letta server, agents, and `/home/adamsl` — lives inside **WSL Ubuntu**, so
that's the target you usually want.

## Quick connect (use Tailscale — it never changes)

| Target | Connect | User |
|--------|---------|------|
| **WSL Ubuntu** (Letta, agents, code) | `ssh adamsl@100.80.49.10` | `adamsl` |
| **Windows 10 host** | `ssh NewUser@100.69.80.89` | `NewUser` |

Both run OpenSSH on port 22. The connecting machine must be on the same Tailnet
(`tailscale status` to confirm).

> ⚠️ **Do not use the LAN IP.** The `10.0.0.x` address is DHCP and drifts on reboot
> (it shifted `10.0.0.143 → 10.0.0.142` on 2026-05-30). Tailscale IPs are stable.
> LAN fallback for the Windows host only: `ssh NewUser@10.0.0.142` — expect it to change.

## Why SSH broke on 2026-05-30

After the Windows reboot at 17:00, two things went wrong:

1. **WSL's `sshd` did not auto-start.** `ssh.service` was `disabled`, so it was down from the
   17:00 reboot until someone started it manually at 19:13 — "connection refused" in between.
2. **The LAN IP drifted** `10.0.0.143 → 10.0.0.142` (DHCP), so anyone using the old LAN address
   hit a dead host.

(The same reboot also left the `letta-server` Docker container down, which is what broke the
Letta ADE — see `~/.claude/commands/letta-admin.md`.)

## Permanent fix — run once in WSL

So `sshd` always comes back after a reboot:

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

Then always connect over Tailscale (`adamsl@100.80.49.10` for WSL). That address never changes,
so reboots can't break it.

> Note: WSL services only auto-start if WSL itself starts on boot and systemd is enabled
> (it is here — `systemctl` works). Docker Desktop on the Windows host auto-starts on **login**,
> not boot, so if the machine reboots and nobody logs in, both Docker containers and (indirectly)
> some services stay down until someone logs into Windows.

## Troubleshooting

```bash
# On the WSL host — confirm sshd is up and set to auto-start:
systemctl is-active ssh        # want: active
systemctl is-enabled ssh       # want: enabled
ss -tlnp | grep :22            # want: 0.0.0.0:22 listening

# Confirm Tailscale is connected (run on BOTH ends):
tailscale status
tailscale ip -4                # WSL should report 100.80.49.10

# End-to-end reachability (proves the box answers over Tailscale):
curl -s http://100.80.49.10:8283/v1/health/   # want: {"status":"ok"}
```

---
*Last verified 2026-05-31. Tailscale node: `desktop-shdbati` (WSL `100.80.49.10`,
Windows host `100.69.80.89`).*
