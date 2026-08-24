"""Borrowing a live WSL_INTEROP socket so a boot-time service can run Windows exes.

The dashboard runs as a `systemd --user` service started at boot, which
inherits no interop relay at all, so every `powershell.exe` call it makes would
fail with "Invalid argument" until it finds one. Everything here exists to find
a socket that genuinely relays and remember it.

Nothing in this module is scanner- or printer-specific; both of those import it.
"""

import os
import subprocess

#: Windows PowerShell, reached through the WSL binfmt interpreter. Named once
#: here because the printer repair and the scanner diagnostics both shell out
#: to it and must agree on the path.
WINDOWS_POWERSHELL = (
    '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')

_INTEROP_CACHE = {'sock': None}
_WIN_CMD_EXE = '/mnt/c/Windows/System32/cmd.exe'


def _interop_works(sock):
    """True if WSL_INTEROP=sock can actually launch a Windows .exe.

    The /init binfmt interpreter fails with "Invalid argument" (non-zero exit)
    when the socket doesn't relay to the Windows side, so a trivial `cmd.exe /c
    exit` is a reliable, fast probe.
    """
    try:
        r = subprocess.run(
            [_WIN_CMD_EXE, '/c', 'exit'],
            env={'PATH': '/usr/bin:/bin', 'WSL_INTEROP': sock},
            capture_output=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _wsl_interop_socket():
    """Return a working WSL_INTEROP socket path, or None.

    The scan script launches Windows `powershell.exe`, which needs a live
    `WSL_INTEROP` relay socket. The dashboard runs as a systemd --user service
    started at boot and inherits no such socket, so powershell.exe fails with
    "Invalid argument". Crucially the /init socket (1_interop/2_interop) does NOT
    relay to Windows — only the per-interactive-session `<pid>_interop` sockets
    do — so we probe candidates (newest first) and cache the first that works.
    Limitation: at least one interactive WSL session must be alive to provide a
    relay; with none open there is no socket the service can borrow.
    """
    cached = _INTEROP_CACHE.get('sock')
    if cached and os.path.exists(cached) and _interop_works(cached):
        return cached
    wsl_run = '/run/WSL'
    cands = []
    try:
        for name in os.listdir(wsl_run):
            if not name.endswith('_interop'):
                continue
            fp = os.path.join(wsl_run, name)
            # Skip the 1_interop symlink and the init socket — they don't relay.
            if os.path.islink(fp) or not os.path.exists(fp):
                continue
            try:
                cands.append((os.path.getmtime(fp), fp))
            except OSError:
                continue
    except OSError:
        return None
    cands.sort(reverse=True)
    for _, fp in cands:
        if _interop_works(fp):
            _INTEROP_CACHE['sock'] = fp
            return fp
    return None
