"""The three token-usage extractors, and the runner that pipes them somewhere.

Each of these is a complete little Python program that runs *on the machine
being measured* -- this box directly, or mom's over SSH -- and prints exactly
one JSON line. They are strings because they have to cross an SSH boundary as
stdin; they are not imported, called, or executed in this process.

That makes them the one kind of code nothing checks: a syntax error in a
90-line `r'''...'''` block is invisible until a card on the dashboard goes
grey. tests/test_model_stats_extractors.py compiles all three and asserts the
contract they share -- one JSON object on stdout, an `error` key instead of a
traceback, no writes to the measured machine.

Keeping them here rather than in server.py is mostly about that: 220 lines of
someone else's language should not sit in the middle of a request handler.
"""

import json
import subprocess
import sys

# Extractors run on the target machine (locally or piped over SSH). Each prints a
# single JSON line so the dashboard parses one stdout blob regardless of host.
_CODEX_EXTRACT_PY = r'''
import json, os, time, urllib.request, urllib.error
home = os.path.expanduser("~")
model = None
try:
    for line in open(os.path.join(home, ".codex", "config.toml")):
        s = line.strip()
        if s.startswith("model") and "=" in s and "reasoning" not in s and "provider" not in s:
            model = s.split("=", 1)[1].strip().strip("\"'"); break
except Exception:
    pass
AUTH = os.path.join(home, ".codex", "auth.json")
def _usage(t):
    req = urllib.request.Request("https://chatgpt.com/backend-api/wham/usage",
        headers={"Authorization": "Bearer " + t["access_token"],
                 "ChatGPT-Account-Id": t.get("account_id", ""),
                 "OpenAI-Beta": "codex-1", "originator": "codex_cli_rs", "User-Agent": "codex"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
def _refresh_token(rt):
    body = json.dumps({"grant_type": "refresh_token", "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
                       "refresh_token": rt, "scope": "openid profile email"}).encode()
    req = urllib.request.Request("https://auth.openai.com/oauth/token", data=body,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
def _persist(d, r):
    t = d["tokens"]
    for k in ("access_token", "refresh_token", "id_token"):
        if r.get(k): t[k] = r[k]
    d["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime())
    json.dump(d, open(AUTH, "w"))
    return t
def _refresh(d):
    return _persist(d, _refresh_token(d["tokens"]["refresh_token"]))
def _heal(d):
    # Codex refresh tokens are single-use/rotating: the live auth.json token may be
    # stale (already consumed) while a backup file still holds a valid one the codex
    # CLI left behind. Try each backup's token; on success persist into auth.json.
    import glob
    for f in sorted(glob.glob(AUTH + "*"), reverse=True):
        if f == AUTH:
            continue
        try:
            rt = json.load(open(f))["tokens"].get("refresh_token")
        except Exception:
            continue
        if not rt:
            continue
        try:
            return _persist(d, _refresh_token(rt)), f
        except Exception:
            continue
    return None, None
out = {"model": model, "as_of": time.time()}
# LIVE usage with SELF-HEAL on 401: refresh via the stored token, and if THAT is
# rejected (invalid_refresh_token), auto-recover from a still-valid backup token.
try:
    d = json.load(open(AUTH)); t = d["tokens"]
    try:
        out["usage"] = _usage(t)
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
        try:
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        except urllib.error.HTTPError:
            healed, src = _heal(d)
            if healed is None:
                raise
            out["usage"] = _usage(healed); out["refreshed"] = True
            out["healed_from"] = os.path.basename(src)
except urllib.error.HTTPError as e:
    code = None
    try:
        code = (json.loads(e.read().decode()).get("error") or {}).get("code")
    except Exception:
        pass
    out["error"] = code or ("HTTP %d" % e.code)
    ra = e.headers.get("Retry-After") if e.headers else None
    if ra:
        try:
            out["retry_after"] = int(ra)
        except ValueError:
            pass
except Exception as e:
    out["error"] = str(e)[:140]
print(json.dumps(out))
'''

_CLAUDE_EXTRACT_PY = r'''
import json, os, time, subprocess, urllib.request, urllib.error
home = os.path.expanduser("~")
CRED = os.path.join(home, ".claude", ".credentials.json")
def _usage(at):
    req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": "Bearer " + at,
                 "anthropic-beta": "oauth-2025-04-20", "User-Agent": "claude-code/2.0.32"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
def _refresh(d):
    o = d["claudeAiOauth"]
    body = json.dumps({"grant_type": "refresh_token", "refresh_token": o["refreshToken"],
                       "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e"}).encode()
    req = urllib.request.Request("https://platform.claude.com/v1/oauth/token", data=body,
        headers={"Content-Type": "application/json", "User-Agent": "anthropic"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _cli_refresh()
        raise
    o["accessToken"] = r["access_token"]
    if r.get("refresh_token"): o["refreshToken"] = r["refresh_token"]
    if r.get("expires_in"): o["expiresAt"] = int((time.time() + r["expires_in"]) * 1000)
    json.dump(d, open(CRED, "w"))
    return o["accessToken"]
def _cli_refresh():
    subprocess.run(["bash", "-lc", 'claude -p "ok"'], capture_output=True, timeout=30)
    d2 = json.load(open(CRED))
    return d2["claudeAiOauth"]["accessToken"]
out = {"as_of": time.time()}
try:
    d = json.load(open(CRED)); o = d["claudeAiOauth"]
    # A logged-out host leaves the credential file in place with BLANK tokens
    # (accessToken == refreshToken == "", expiresAt == 0). Sending
    # "Authorization: Bearer " unauthenticated gets a 429 from Anthropic's edge,
    # which used to render as "usage stats RATE LIMITED" — a yellow tile blaming
    # a throttle that would never clear on its own. Detect it before any network
    # call and report the condition by name.
    if not (o.get("accessToken") or "").strip() and not (o.get("refreshToken") or "").strip():
        out["condition"] = "logged_out"
        out["error"] = "logged out (no OAuth token on this host)"
        print(json.dumps(out)); raise SystemExit(0)
    expired = bool(o.get("expiresAt")) and o["expiresAt"] / 1000 < time.time() + 60
    try:
        if expired:
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        else:
            out["usage"] = _usage(o["accessToken"])
    except urllib.error.HTTPError as e:
        # A 401 means the credential needs refreshing. A 429 comes from the
        # separate usage endpoint and must be surfaced without running Claude
        # (which only adds traffic while quota reporting is throttled).
        if e.code == 401:
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        else:
            raise
except urllib.error.HTTPError as e:
    out["error"] = "HTTP %d" % e.code
    out["condition"] = "rate_limited" if e.code == 429 else "unknown"
    ra = e.headers.get("Retry-After") if e.headers else None
    if ra:
        try:
            out["retry_after"] = int(ra)
        except ValueError:
            pass
except Exception as e:
    out["error"] = str(e)[:140]
try:
    sc = json.load(open(os.path.join(home, ".claude", "stats-cache.json")))
    days = sc.get("dailyModelTokens") or []
    if days:
        tbm = (days[-1].get("tokensByModel") or {})
        if tbm:
            out["recent_model"] = max(tbm, key=lambda k: sum(tbm[k].values()) if isinstance(tbm[k], dict) else tbm[k])
except Exception:
    pass
print(json.dumps(out))
'''

# 2026-08-16: this card used to monitor Google's Antigravity CLI (`agy`), an
# entirely different product from the Gemini *API* (generativelanguage.
# googleapis.com) that GEMINI_API_KEY authenticates against and that the
# dashboard's own "Gemini Flash Fill" button (finance/manual_entry.py's
# gemini-only preview engine) actually spends -- EG initially assumed Gemini
# itself had been deprecated in favor of Antigravity; confirmed via search
# that's wrong (the retired product was the old Gemini *CLI*, a chat/coding
# tool; Antigravity is its replacement and now runs *on top of* the still-
# current Gemini API, not instead of it). Antigravity CLI usage was never the
# thing this dashboard actually spends, so it's replaced here with real
# monitoring for the key that is: the same "count real calls seen in a local
# log" approach as Antigravity used, applied to
# parse_and_categorize.py's own GEMINI_API_USAGE_LOG (~/.gemini/
# receipt_api_usage.log), written by _log_gemini_api_call() on every actual
# API attempt. There is no usage-query endpoint for a bare API key the way
# Antigravity's OAuth session has loadCodeAssist, so unlike that card's real
# Google-reported tier/limit, the "limit" here is a locally-configured
# estimate (GEMINI_FLASH_FILL_DAILY_LIMIT env var, default 250 -- Google's
# published free-tier gemini-2.5-flash RPD as of this writing), not
# authoritative -- flagged as such in the card's detail text.
_GEMINI_FLASH_FILL_EXTRACT_PY = r'''
import datetime, json, os
USAGE_LOG = os.path.expanduser("~/.gemini/receipt_api_usage.log")
DAILY_LIMIT = int(os.environ.get("GEMINI_FLASH_FILL_DAILY_LIMIT", "250"))
out = {"configured": False, "used": 0, "limit": DAILY_LIMIT, "resets_at": None, "error": None}

def _find_gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        with open(os.path.expanduser("~/rol_finances/.env")) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None

key = _find_gemini_key()
out["configured"] = bool(key)
if not key:
    out["error"] = "GEMINI_API_KEY not set (~/rol_finances/.env)"
else:
    today = datetime.date.today()
    used = 0
    try:
        with open(USAGE_LOG) as fh:
            for line in fh:
                try:
                    ts = json.loads(line).get("ts")
                except Exception:
                    continue
                if ts and datetime.datetime.fromtimestamp(ts).date() == today:
                    used += 1
    except FileNotFoundError:
        pass  # no calls logged yet today (or ever) -- used stays 0, not an error
    out["used"] = used
    # Same reset convention as every other Google per-day cap on this card
    # (Antigravity/Code Assist included): midnight Pacific.
    try:
        from zoneinfo import ZoneInfo
        pt = ZoneInfo("America/Los_Angeles")
        now = datetime.datetime.now(pt)
        nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        out["resets_at"] = nxt.astimezone(datetime.timezone.utc).isoformat()
    except Exception:
        pass
print(json.dumps(out))
'''

def _run_extractor(py_src, host, timeout=18):
    """Run an extractor on a machine (local if host is None, else over SSH) and
    return its parsed JSON, or {'error': ...}."""
    try:
        if host:
            # Feed the script over stdin (`python3 -`) so the remote shell can't
            # mangle a multi-line `-c` argument.
            cmd = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', host, 'python3', '-']
        else:
            cmd = [sys.executable, '-']
        r = subprocess.run(cmd, input=py_src, capture_output=True, text=True, timeout=timeout)
        line = (r.stdout or '').strip().splitlines()[-1] if (r.stdout or '').strip() else ''
        return json.loads(line) if line else {'error': (r.stderr or 'no output')[:200]}
    except Exception as e:
        return {'error': str(e)}
