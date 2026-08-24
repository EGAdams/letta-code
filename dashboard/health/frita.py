"""The Claude-SDK executor the Mazda minions actually run their work on.

Green here means one specific thing: an SDK-capable executor answered on
:8799 with the SDK, the Claude CLI and a valid credential all present.

The rest of this module exists because of a recurring failure that took a long
time to diagnose the first time. The live letta-server runs in a separate
containerd stack whose own `frita-executor` DNS name resolves to a *stale*
executor with no SDK, and that ghost surfaces on :8797. Both ports are probed,
and when a different container answers the second one the condition is named in
the status text -- so nobody has to hunt for it again.

Two smaller decisions worth knowing:

  * The work route (`/claude_sdk`, the one the minions POST to) is probed
    separately from the status route. The status endpoint can be perfectly
    healthy while the work route 404s, which is the exact failure Frita hit.
  * The probe is a GET, never a POST. POSTing a real job would launch an SDK
    run on every health sweep.

And one that makes this more than a report: a `creds_valid: false` reading is
the single failure mode this box can repair itself, by re-pushing the current
OAuth token, so the check tries that once before calling the executor down.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request

from health.probe import probe

# Frita / Claude-SDK executor endpoints. The Mazda minions reach the SDK
# executor via the host bridge on :8799 (the live letta-server runs in a
# separate containerd "ghost" stack whose own `frita-executor` DNS points at a
# stale no-SDK executor — see frita_executor_ghost_container memory). :8797 is
# where that stale ghost typically surfaces, so we watch it explicitly.
FRITA_EXEC_GOOD_URL = 'http://100.80.49.10:8799/claude_sdk_status'
FRITA_EXEC_GHOST_URL = 'http://100.80.49.10:8797/claude_sdk_status'
# The actual WORK endpoint the minions' run_claude_code_sdk tool POSTs to. The
# status endpoint above can be perfectly healthy while THIS route 404s — which
# is exactly the "HTTP Error 404: Not Found" Frita hit. We probe it cheaply so
# the affected agents' tabs go red. See agent_health_check / uses_claude_sdk.
FRITA_EXEC_WORK_URL = 'http://100.80.49.10:8799/claude_sdk'
# The push side of claude-creds-sync.{timer,path,service} (see
# server_tools/sync_claude_creds_to_frita.sh) — this box's Claude OAuth token
# refreshes constantly via normal use, but the copy pushed to the executor's
# frita-claude-home can still go stale in the gap before the next sync fires.
# frita_executor_health() runs this directly on a creds_valid:false reading so
# a health *check* also fixes the thing it found broken, instead of just
# reporting yellow until claude-creds-sync.path/timer gets around to it.
FRITA_CREDS_SYNC_SCRIPT = os.path.expanduser('~/server_tools/sync_claude_creds_to_frita.sh')


def _resync_frita_creds(timeout):
    """Best-effort: re-push this box's current Claude OAuth token to the
    frita-executor. Returns True iff the script ran and exited 0 — a non-zero
    exit (e.g. local token itself expiring within 5min) just means "can't help
    right now", not an error worth raising."""
    try:
        r = subprocess.run([FRITA_CREDS_SYNC_SCRIPT], capture_output=True,
                            timeout=timeout, text=True)
        return r.returncode == 0
    except Exception:
        return False


def _probe_claude_sdk_endpoint(url, timeout):
    """Cheap reachability probe of the /claude_sdk WORK route. Returns one of:

      'ok'          — the route exists (any non-404 response, including a 405
                      'method not allowed' for our GET against a POST-only route,
                      or even a 4xx/5xx — the point is the path is mounted).
      'not_found'   — HTTP 404: the route the tool POSTs to is missing. This is
                      Frita's exact failure; the affected tabs must go red.
      'unreachable' — connection refused / timeout / DNS — executor is down.

    Deliberately does NOT POST a real job (that would launch an SDK run on every
    health sweep); a GET is enough to tell 'route missing' from 'route present'."""
    try:
        req = urllib.request.Request(url, method='GET')
        urllib.request.urlopen(req, timeout=timeout)
        return 'ok'
    except urllib.error.HTTPError as e:
        return 'not_found' if e.code == 404 else 'ok'
    except Exception:
        return 'unreachable'


def _probe_sdk_status(url, timeout):
    """GET a /claude_sdk_status endpoint; return parsed dict or None on failure."""
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read(2000).decode('utf-8', errors='replace'))
    except Exception:
        return None


def frita_executor_health(timeout=None):
    """Health for the Claude-SDK executor that the Mazda minions actually use.

    GREEN only when the SDK-capable executor answers on :8799 (sdk + claude CLI
    + mom's-token creds all present). Also probes :8797 and, if a *different*
    no-SDK executor answers there, flags the recurring "ghost / duplicate stack"
    condition right in the status text so it never has to be hunted down again."""
    t = timeout or 6
    good = _probe_sdk_status(FRITA_EXEC_GOOD_URL, t)
    ghost = _probe_sdk_status(FRITA_EXEC_GHOST_URL, t)

    # Ghost detection on :8797. Three cases, in order:
    #  1) it answers the new status endpoint but is NOT SDK-ready, or is a
    #     different container than the good one on :8799  → confirmed ghost.
    #  2) status endpoint 404s but the old /health still answers → a stale
    #     executor running pre-status-endpoint code → also a ghost.
    #  3) nothing answers :8797 → clean, no ghost.
    ghost_warn = ''
    good_host = (good or {}).get('host')
    if ghost is not None:
        ghost_host = ghost.get('host')
        if not ghost.get('ready') or (good_host and ghost_host and ghost_host != good_host):
            ghost_warn = f' ⚠ GHOST on :8797 (host={ghost_host}, sdk={ghost.get("sdk_present")})'
    else:
        ghost_health = _probe_sdk_status('http://100.80.49.10:8797/health', t)
        if ghost_health is not None:
            ghost_warn = ' ⚠ GHOST on :8797 (stale executor, no SDK-status endpoint)'

    if good is None:
        return probe(False,
                     'SDK executor UNREACHABLE on :8799 — Mazda minions cannot run '
                     'run_claude_code_sdk. Click "Start" to redeploy.' + ghost_warn)
    if not good.get('ready'):
        missing = [k for k in ('sdk_present', 'claude_present', 'creds_present')
                   if not good.get(k)]
        if good.get('claude_runs') is False:
            missing.append('claude_runs')
        # creds_present-but-expired is the one failure mode this box can fix by
        # itself (re-push a fresh token) rather than needing a redeploy — try
        # that once before reporting down. See _resync_frita_creds.
        if good.get('creds_present') and good.get('creds_valid') is False:
            missing.append('creds_valid')
            if _resync_frita_creds(t):
                healed = _probe_sdk_status(FRITA_EXEC_GOOD_URL, t)
                if healed and healed.get('ready'):
                    return probe(True,
                                 f'SDK OK on :8799 (host={healed.get("host")}) — '
                                 'auto-resynced an expired token.' + ghost_warn,
                                 concern=True)  # surfaced, but self-healed this sweep
        if good.get('claude_runs') is False:
            runtime_msg = good.get('claude_error') or 'claude --version failed'
            return probe(False,
                         f'SDK executor on :8799 NOT ready (Claude runtime failed: '
                         f'{runtime_msg}; path={good.get("claude_path")}; '
                         f'host={good.get("host")}) — minions broken.' + ghost_warn)
        return probe(False,
                     f'SDK executor on :8799 NOT ready (missing: {", ".join(missing)}; '
                     f'host={good.get("host")}) — minions broken.' + ghost_warn)
    return probe(True,
                 f'SDK OK on :8799 (host={good.get("host")}; '
                 f'claude={good.get("claude_version") or "unknown"}).' + ghost_warn,
                 # up, but a shadowing ghost → yellow, not green
                 concern=bool(ghost_warn))
