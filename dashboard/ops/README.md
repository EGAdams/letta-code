# Dashboard availability ops (DESKTOP-2OBSQMC)

These scripts keep the ROL Finance dashboard (`:8765`) up on **DESKTOP-2OBSQMC**, which runs two
WSL distros. They are specific to that machine's layout — do not install them elsewhere without
reading "Scope" below.

## The failure this fixes

Repeating outages on 2026-07-17 / 07-21 / 07-22 (five of them, the last two within ten minutes),
all presenting as "the dashboard URL is down" or a 502 from the tailnet front.

Chain of causation:

1. Nothing on the Windows side held **Ubuntu-26.04** open, so WSL periodically tore the whole
   distro down — `WSL (1 - init()) ERROR: InitEntryUtilityVm:2555: Init has exited. Terminating
   distribution`. A stopped distro means no listener on `:8765` at all.
2. Each teardown left processes in the `user@1000.service` cgroup tree that read as PID `0`
   (foreign PID namespace). `user@1000.service: Processes still around after final SIGKILL.`
3. The next start then failed with `Failed to spawn executor: Device or resource busy`, so
   **every** user service stayed dead: `dashboard-server`, `lettabot`, `thought-bridge`,
   `thought-bridge-monitor`, `mazda-tools-mcp`, `mazda-executor`.

**The previously documented recovery was making it worse.** It called `loginctl terminate-user`,
which returns immediately but completes 25–70s later — tearing down the session that had just been
restarted. That is the real explanation for the "it re-wedged on its own after about 60 seconds"
reports: each repair scheduled the next outage. It also ran a blind `rmdir` sweep that raced
`cgroup.kill`, so the stale cgroups were never actually cleared.

`cgroup.kill` *does* clear the PID-`0` entries. The belief that they were unkillable came from the
racing `rmdir`, not from the kill failing.

## What is installed

| Artifact | Location on 2OBSQMC | Purpose |
|---|---|---|
| `fix-user-session.sh` | `/home/adamsl/bin/` in Ubuntu-26.04 | Clears a wedged `user@1000` cgroup tree and restarts it. Logs to `~/fix-user-session.log`. |
| `hold-ubuntu2604.ps1` | `C:\Users\NewUser\` | Infinite loop holding one WSL client open so the distro is never terminated. Run by task `ROL WSL26 Holder` (`/sc onlogon`). |
| `keep-dashboard-up.ps1` | `C:\Users\NewUser\` | Watchdog. Run by task `ROL Dashboard Keepalive` every 2 min. Logs to `C:\Users\NewUser\keep-dashboard-up.log`. |

Watchdog escalation order: holder task not running → start it; `user@1000` not active → run the
recovery via `systemd-run`; dashboard not answering 200 on two consecutive probes → restart
`dashboard-server.service`.

Also masked in Ubuntu-26.04 (originals moved to `~/disabled-units/`):

- `dashboard-browser.service` — auto-opened Chrome on login; the main generator of stuck
  foreign-PID cgroup entries. **Side effect: the dashboard no longer opens a browser window
  automatically.**
- `openclaw-gateway.service` — crash-looped every 5s on a missing `/usr/local/bin/node`.

And in the Ubuntu-24.04 stub, `dashboard-server.service` is masked to `/dev/null` (original in
`~/disabled-units-stub/`) so it can never race for `:8765` again. `disable` and renaming the unit
file were both tried before and proved insufficient; a `/dev/null` symlink is refused by systemd
no matter what re-enables it.

## Rules learned the hard way

- **Never use `loginctl terminate-user` in this recovery.** See above.
- Wait for `cgroup.procs` to actually drain before `rmdir`-ing the directories.
- Launch the recovery with `systemd-run`, **not** `setsid nohup … &`. Under
  `ssh → wsl.exe -e bash -lc`, a backgrounded script is killed when the WSL session ends — the log
  file was never even created while the watchdog happily reported it had "launched".
- `wsl.exe -t Ubuntu-26.04` does **not** clear the wedge; the cgroup tree lives in the shared WSL2
  utility VM and survives a distro terminate. `wsl --shutdown` is not needed either.
- Do not create the holder with PowerShell `Start-Process -ArgumentList` — array quoting mangles
  `bash -c '...'` and the process silently never starts.
- Do not probe for the holder with an anchored regex through `wsl.exe -e bash -lc` (`^sleep 3600$`);
  the anchors do not survive the nested quoting and it misreports. Query the scheduled task state
  on the Windows side instead.
- A `curl` 200 proves nothing about which distro answered. Verify by MainPID:
  `systemctl --user show dashboard-server.service -p MainPID` must equal the `ss -tlnp | grep 8765`
  owner.

## Manual recovery

```bash
ssh NewUser@100.118.122.75 "wsl.exe -d Ubuntu-26.04 -e bash -lc \
  \"sudo -n systemd-run --unit=fix-user-session --collect /home/adamsl/bin/fix-user-session.sh\""
```

Then confirm, roughly 90s later:

```bash
systemctl is-active user@1000.service          # active
ss -tlnp | grep 8765                            # owned by dashboard-server's MainPID
curl -s -o /dev/null -w '%{http_code}' http://localhost:8765/
```

Diagnostic that localizes a wedge (as root in Ubuntu-26.04) — `0` entries are the stuck ones:

```bash
for f in $(find /sys/fs/cgroup/user.slice/user-1000.slice -name cgroup.procs); do
  c=$(cat "$f" 2>/dev/null | tr '\n' ' '); [ -n "$c" ] && echo "$f => $c"; done
```

## Scope

This applies **only to DESKTOP-2OBSQMC**, which is the sole machine running the dashboard and the
only one with the Ubuntu-24.04 / Ubuntu-26.04 two-distro split. The Windows scheduled tasks and the
systemd unit masks are per-machine state and are not reproduced by a `git pull`; on that box they
are already installed. Other machines need nothing from this directory.
