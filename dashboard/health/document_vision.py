"""Can Mazda read a scanned page at all, and can she categorise what she read.

Two tiles, two different chains, deliberately kept apart in one module because
they read the same event log and confusing them sends the operator to the wrong
runbook.

*Document Vision* mirrors the fallback chain in tools/classify_scan.py --
Gemini key, then the Codex CLI's ChatGPT OAuth session, then a standalone
OpenAI key -- and reports how many of the three are usable. It checks presence
and expiry only, never spending a paid call to find out. Green needs two tiers,
so one Codex token that has not refreshed yet does not cry wolf; yellow at
exactly one, which is one outage from a halt; red only when all three are gone,
which is the condition `process_scanned_document` refuses to dispatch into.

*Categorizer* covers the later vendor-categorisation chain, and reads real
outcomes rather than credentials. It exists because in 2026-07 the gemini CLI
was missing on the executor for three days and nothing showed it: every receipt
degraded quietly to a null-category pending-review row, which looks exactly
like normal operation unless somebody is counting.

The subtlety worth preserving is `unresolved_fallbacks`. A fallback stops being
worth alerting on the moment the tier it fell back *from* records a later
success. Without that check one rate-limit blip held the tile yellow for a full
24 hours -- observed with an 11-second recovery still showing NEEDS ATTENTION
sixteen hours later. A tile that cries wolf is a tile nobody reads, which
defeats the entire point of building it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from health.failures import classify_failure
from health.probe import probe
from paths import ROL_FINANCES_DIR

ROL_FINANCES_ENV_PATH = os.path.join(ROL_FINANCES_DIR, '.env')



def _read_env_var(name, env_path=None):
    """Look up name in os.environ, falling back to a simple KEY=VALUE .env file.

    env_path defaults to the CURRENT value of ROL_FINANCES_ENV_PATH, read at
    call time (not as a mutable-default-arg frozen at def time), so tests can
    monkeypatch server.ROL_FINANCES_ENV_PATH and have it take effect."""
    val = os.environ.get(name)
    if val:
        return val
    if env_path is None:
        env_path = ROL_FINANCES_ENV_PATH
    try:
        for line in open(env_path):
            line = line.strip()
            if line.startswith(f'{name}='):
                return line.split('=', 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


def _jwt_claims(token):
    """Best-effort decode of a JWT's payload (no signature check — we only need exp)."""
    import base64
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def document_vision_health(timeout=None):
    """Health of the receipt/statement scan-classification vision chain.

    Checks the SAME three tiers classify_scan.py tries, in order, without
    spending any API budget: Gemini key present, Codex CLI OAuth access_token
    present and unexpired, standalone OpenAI key present."""
    tiers_up = []
    tiers_down = []

    gemini_key = _read_env_var('GEMINI_API_KEY') or _read_env_var('GOOGLE_API_KEY')
    if gemini_key:
        tiers_up.append('Gemini')
    else:
        tiers_down.append('Gemini (no GEMINI_API_KEY/GOOGLE_API_KEY)')

    codex_auth_path = os.path.expanduser('~/.codex/auth.json')
    try:
        auth = json.load(open(codex_auth_path))
        access_token = auth.get('tokens', {}).get('access_token', '')
        exp = _jwt_claims(access_token).get('exp', 0)
        if access_token and exp > time.time():
            tiers_up.append('ChatGPT-OAuth (Codex CLI)')
        else:
            tiers_down.append('ChatGPT-OAuth (Codex CLI token expired)')
    except (OSError, json.JSONDecodeError, AttributeError):
        tiers_down.append('ChatGPT-OAuth (no ~/.codex/auth.json)')

    if _read_env_var('OPENAI_API_KEY'):
        tiers_up.append('OpenAI key')
    else:
        tiers_down.append('OpenAI key (not configured)')

    n_up = len(tiers_up)
    text = f'{n_up}/3 vision tiers available: {", ".join(tiers_up) or "none"}.'
    if tiers_down:
        text += f' Down: {", ".join(tiers_down)}.'

    if n_up == 0:
        return probe(False,
                     'ALL vision tiers down — Mazda cannot classify or read '
                     'scanned documents. ' + text)

    # Credential presence alone can't see a tier that authenticates but then
    # fails every real call, so also surface unrecovered vision fallbacks from
    # the shared provider_health event log. These used to land on the
    # Categorizer tile, which owns a different chain and a different remedy.
    vision_fallbacks = vision_provider_fallbacks()
    if vision_fallbacks:
        text += f' {vision_fallbacks}'
    return probe(True, text, concern=n_up == 1 or bool(vision_fallbacks))


def vision_provider_fallbacks():
    """Summary of unrecovered vision-tier fallbacks, or '' when there are none.

    Read-only and best-effort: a missing/corrupt event log must never turn the
    Document Vision tile red on its own — the credential checks above are the
    tile's primary signal."""
    try:
        with open(MAZDA_PROVIDER_HEALTH_PATH) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ''
    all_accounts, fallback_events = split_provider_health_state(state)
    events = unresolved_fallbacks(
        all_accounts, fallback_events,
        time.time() - MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS, want_vision=True)
    if not events:
        return ''
    summary = '; '.join(
        f'{provider} {ev["from"]}->{ev["to"]} ({classify_failure(ev.get("error", ""))[1]})'
        for provider, ev in events[-5:]
    )
    return f'{len(events)} unrecovered vision fallback(s) in last 24h: {summary}'


MAZDA_PROVIDER_HEALTH_PATH = os.path.expanduser('~/.mazda/provider_health.json')
MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS = 24 * 3600

# provider_health.json is one shared event log covering two INDEPENDENT LLM
# chains, each owned by its own dashboard tile: the vendor-categorization chain
# (Categorizer tile) and the scan-classification chain (Document Vision tile).
# Only the vision providers are self-identifying; `gemini`/`anthropic`/`openai`
# are recorded under bare keys because the recorder in rol_finances doesn't tag
# which chain called them, so they stay with the Categorizer tile as before.
VISION_PROVIDER_PREFIX = 'chatgpt-oauth-vision'


def provider_belongs_to_vision(provider):
    """True for providers the Document Vision tile owns."""
    return provider.startswith(VISION_PROVIDER_PREFIX)


def split_provider_health_state(state):
    """Split a raw provider_health.json mapping into
    ({account_key: entry}, {provider: [event, ...]})."""
    account_entries = {}
    fallback_events = {}
    for key, entry in state.items():
        if key.endswith(':_fallbacks'):
            fallback_events[key.rsplit(':', 1)[0]] = list(entry.get('events', []))
        else:
            account_entries[key] = entry
    return account_entries, fallback_events


def unresolved_fallbacks(account_entries, fallback_events, cutoff, want_vision):
    """Fallback events inside the window that are still worth alerting on.

    A fallback is *resolved* — and therefore NOT alert-worthy — once the account
    it fell back FROM has recorded a success later than the fallback itself.
    Without this check a single rate-limit blip kept the tile yellow for a full
    24h even though the very next call succeeded seconds later (observed
    2026-08-08: EG's ChatGPT cap reset, the primary tier recovered 11s after the
    fallback, and the tile still read NEEDS ATTENTION ~16h afterwards). Alerting
    on an already-recovered condition trains the operator to ignore the tile,
    which is exactly the blindness this tile was built to prevent.
    """
    out = []
    for provider, events in fallback_events.items():
        if provider_belongs_to_vision(provider) != want_vision:
            continue
        for ev in events:
            when = ev.get('time', 0)
            if when < cutoff:
                continue
            origin = account_entries.get(f'{provider}:{ev.get("from")}', {})
            if origin.get('last_success', 0) > when:
                continue  # primary tier already recovered
            out.append((provider, ev))
    return out


def mazda_categorizer_fallback_health(timeout=None):
    """Health of the vendor-CATEGORIZATION LLM chain (STEP 3 of receipt intake:
    tools/categorizer/categorizer_main.py's gemini -> chatgpt-oauth (EG's
    account, then mom's) -> anthropic tiers). Distinct from document_vision_health
    above, which covers the earlier vision-CLASSIFICATION step and only checks
    credential presence, not real call outcomes.

    WHY THIS EXISTS: on 2026-07-20 the gemini CLI was missing/quota-exhausted
    on the executor for 3+ days before anyone noticed — every receipt just
    silently degraded to a null-category pending-review row, which looked like
    normal operation everywhere except a pile of NEEDS_VENDOR_KEY rows nobody
    was watching for. This reads tools/provider_health.py's event log (written
    by every real production call, not a synthetic probe — never burns quota
    just to monitor) so a provider going bad shows up here within one scan
    instead of days later."""
    try:
        with open(MAZDA_PROVIDER_HEALTH_PATH) as f:
            state = json.load(f)
    except FileNotFoundError:
        return probe(True, 'no categorizer LLM calls logged yet')
    except (OSError, json.JSONDecodeError) as e:
        return probe(False, f'cannot read {MAZDA_PROVIDER_HEALTH_PATH}: {e}')

    now = time.time()
    cutoff = now - MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS

    all_accounts, fallback_events = split_provider_health_state(state)
    # Vision providers are the Document Vision tile's business, not this one's —
    # a vision-tier fallback lighting up the Categorizer tile sends the operator
    # to the wrong runbook.
    account_entries = {
        key: entry for key, entry in all_accounts.items()
        if not provider_belongs_to_vision(key)
    }
    recent_fallbacks = unresolved_fallbacks(
        all_accounts, fallback_events, cutoff, want_vision=False)

    if not account_entries:
        return probe(True, 'no categorizer LLM calls logged yet')

    # "down" only when EVERY tracked provider:account's most recent event was
    # a failure — i.e. every known tier (including mom's fallback account) has
    # failed, not just one link in the chain that a later tier covered for.
    most_recent_per_account = []
    for key, entry in account_entries.items():
        last_success = entry.get('last_success', 0)
        last_failure = entry.get('last_failure', 0)
        most_recent_per_account.append((key, last_success >= last_failure, entry))

    all_last_failed = all(not ok for _, ok, _ in most_recent_per_account)

    if all_last_failed:
        details = '; '.join(
            f'{key}: {classify_failure(entry.get("last_failure_detail", ""))[1]}'
            for key, _, entry in most_recent_per_account
        )
        # `hard`: no Restart button. Every remedy here -- a quota reset, a new
        # key, an interactive login -- is somewhere this box cannot reach.
        return probe(False,
                     f'ALL categorizer LLM tiers currently failing — {details}. '
                     f'Receipts will degrade to null-category pending-review rows.',
                     hard=True)

    if recent_fallbacks:
        summary = '; '.join(
            f'{provider} {ev["from"]}->{ev["to"]} ({classify_failure(ev.get("error",""))[1]})'
            for provider, ev in recent_fallbacks[-5:]
        )
        return probe(True,
                     f'{len(recent_fallbacks)} unrecovered fallback(s) in last 24h: {summary}',
                     concern=True)

    return probe(True,
                 f'{len(account_entries)} provider account(s) healthy on primary tier')


def restart_mazda_categorizer_llm():
    """'Restart' for the LLM Provider Fallbacks tile: there's no service to
    bounce (this reads an event log, not a running process). The one real
    recovery action available here is re-pulling mom's cached Codex token
    (sync_moms_codex_token.sh) in case it just needed a refresh — then
    re-report current status. EG's own token/gemini quota/anthropic key have
    no remote fix a dashboard button can perform."""
    try:
        r = subprocess.run(
            [os.path.expanduser('~/server_tools/sync_moms_codex_token.sh')],
            capture_output=True, text=True, timeout=30)
        sync_note = (r.stdout or r.stderr or '').strip()[:200]
    except Exception as exc:
        sync_note = f'sync script error: {exc}'
    health = mazda_categorizer_fallback_health()
    return probe(health['ok'],
                 f'Re-synced mom\'s Codex token ({sync_note}). {health["text"]}')


DOCUMENT_VISION_HALT_MESSAGE = (
    'Scan NOT dispatched to Mazda: all document-vision tiers are down '
    '(Gemini key, ChatGPT-OAuth/Codex CLI, and OpenAI key all unavailable) — '
    'she has no way to classify or read the scanned image right now. '
    'Fix at least one vision tier, then use "Process Document" to retry.'
)
