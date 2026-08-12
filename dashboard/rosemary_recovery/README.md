# Shelia / Rosemary46 Recovery

Shelia is a Letta agent backed by a deliberately narrow Windows-side service.
The service is not a shell and accepts no command strings. It exposes status,
keepalive start, fixed WSL `tailscaled` restart, interactive reauthentication
instructions, and fixed SSH verification.

## One-time local install on Rosemary46

Copy this directory to Rosemary46, open **Administrator PowerShell**, and run:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$token = [Convert]::ToBase64String($bytes)
.\install_rosemary.ps1 -RecoveryToken $token
Start-ScheduledTask -TaskName 'Shelia Rosemary46 Recovery Service'
```

The token must be provisioned into Shelia’s Letta tool environment as
`SHELIA_RECOVERY_TOKEN`; it is never committed or printed by the provisioning
script. The Letta host must be able to reach `http://100.106.176.58:8795` over
Tailscale. The service binds only to Rosemary46's Tailscale address and the
installer permits inbound traffic only from the Letta host. Tailscale encrypts
the bearer-token transport. If either address changes, update the service
environment and firewall rule together. If the node key is expired, complete
Tailscale login locally first.

The recovery service and the existing `Rosemary46 WSL Tailscale Keepalive`
scheduled task are separate. Installation does not create the keepalive task;
the recovery service starts and inspects that pre-installed task.

## Bootstrap limitation

Shelia cannot bootstrap a completely powered-off Windows host or an expired
Tailscale identity. Local or out-of-band Windows access remains the root of
trust. Once this service is installed and authenticated, Shelia can start the
keepalive task and verify SSH without arbitrary remote shell access.