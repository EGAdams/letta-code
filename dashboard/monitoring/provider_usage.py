"""How much quota is left on the account the Letta fleet is actually spending?

Every agent in `LETTA_AGENTS` is tagged with an `llm_provider`, and the Letta
server spends *that provider row's* OAuth token when the agent talks to a
model. So the only honest way to ask "will the next message go through" is to
read the same token out of `/v1/providers/` and ask the vendor's own usage
endpoint. That is what this module does, for zero LLM tokens -- which is the
entire point. The predecessor was a canary that sent a real `ping` message to
an agent and burned roughly forty full-context calls an hour against the very
quota it was watching (2026-07-07).

The pieces are one pipeline, read top to bottom:

    provider_agent_ids   -- who is affected if this account is capped
    fetch_oauth_creds    -- the token Letta itself would spend
    probe_*_usage        -- GET the vendor usage endpoint with it
    classify_*_usage     -- turn the payload into {'ok', 'text'}

`classify_*` is where the typing lives, and the reason is in `CodexUsage`
below: the verdict these two functions return is what decides whether the
ChatGPT failover swap fires, and before this round an unrecognised payload
produced a confident "plenty of headroom".

Only the agent roster stays behind in `server.py` -- `LETTA_AGENTS` and
`get_letta_id` arrive in a `Collaborators` bundle built fresh per call, so
replacing either on `server` is honoured by the code that actually runs.
`LETTA_BASE_URL` is imported instead: it already has its own home in
`hosts.py`, and injecting it would be ceremony.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from hosts import LETTA_BASE_URL
from model_stats.windows import _human_reset


@dataclass(frozen=True)
class Collaborators:
    """What still lives in server.py. Build it per call, never at import."""
    agents: Iterable[dict]
    get_letta_id: Callable[[dict], str | None]


# ── The payloads ─────────────────────────────────────────────────────────────

class CodexWindow(BaseModel):
    """One ChatGPT usage window.

    `used_percent` is required and may not be null. It used to be read as
    ``float(w.get('used_percent') or 0)``, which turns both "the field is gone"
    and "the field is null" into the single most reassuring number the tile can
    show. A window that declines to say how full it is is not an empty window.
    """
    model_config = ConfigDict(extra='allow')

    used_percent: float
    reset_at: Any = None
    limit_window_seconds: float | None = None


class CodexRateLimit(BaseModel):
    model_config = ConfigDict(extra='allow')

    allowed: bool = True
    limit_reached: bool = False
    primary_window: CodexWindow | None = None
    secondary_window: CodexWindow | None = None


class CodexUsage(BaseModel):
    """A chatgpt.com/backend-api/wham/usage body, refused unless it says something.

    This is the untyped boundary with the most expensive silent failure in the
    dashboard. `_classify_codex_usage` read the body as
    ``usage.get('rate_limit') or {}`` and then asked it three optional
    questions, so a body whose shape had moved -- a renamed key, an error
    envelope, a login page -- produced no windows, no `limit_reached`, and
    therefore ``{'ok': True, 'text': ''}``: a confident all-clear. That verdict
    is what `_maybe_chatgpt_failover` consults, so the failure mode was the
    fleet sitting on an exhausted account while the dashboard showed a green
    tile with nothing written on it.

    The validator refuses exactly the payloads that would have produced that:
    no window *and* no explicit "you are capped" flag. It can never turn a real
    limited verdict into an error -- `limit_reached` or ``allowed: false`` is
    evidence on its own, and is accepted with no window at all.
    """
    model_config = ConfigDict(extra='allow')

    rate_limit: CodexRateLimit

    @model_validator(mode='after')
    def _must_carry_a_verdict(self) -> 'CodexUsage':
        rl = self.rate_limit
        if rl.primary_window is None and rl.secondary_window is None \
                and not rl.limit_reached and rl.allowed:
            raise ValueError('no usage window and no cap flag in the body')
        return self


class ClaudeWindow(BaseModel):
    model_config = ConfigDict(extra='allow')

    utilization: float
    resets_at: Any = None


class ClaudeUsage(BaseModel):
    """An api.anthropic.com/api/oauth/usage body. Same contract as the Model
    Stats extractor: five_hour / seven_day utilization.

    Refused when neither window is present, for the same reason as CodexUsage
    but with a worse old answer: the missing windows were read as
    ``utilization: 0``, so an unrecognised body rendered as
    ``5h 0% / weekly 0%`` -- not merely a confident all-clear but a specific,
    plausible, wrong number.
    """
    model_config = ConfigDict(extra='allow')

    five_hour: ClaudeWindow | None = None
    seven_day: ClaudeWindow | None = None

    @model_validator(mode='after')
    def _must_carry_a_window(self) -> 'ClaudeUsage':
        if self.five_hour is None and self.seven_day is None:
            raise ValueError('no five-hour or seven-day window in the body')
        return self


class UsagePayloadError(ValueError):
    """A usage body this module can no longer read.

    Its own type, and its message is curated rather than pydantic's, for a
    reason that is not cosmetic: `classify_failure()` decides what a failure
    *is* by substring, and one of the substrings it looks for is
    ``rate_limit`` -- the name of the very field the ChatGPT payload puts the
    windows in. Report a shape change with the vendor's field names in it and
    the dashboard labels it "rate-limited", which is the precise misdiagnosis
    `classify_failure` was written to stop (see its docstring: a 404 reported
    as rate-limited "sent diagnosis down the wrong path").
    """


#: Path elements that would make classify_failure() misread a shape error.
#: Dropping them costs a little precision in the message and buys the operator
#: the right label.
_FAILURE_CLASS_TRIGGERS = ('rate limit', 'rate-limit', 'rate_limit', 'quota',
                           'too many requests', '429')


def _shape_detail(error: ValidationError) -> str:
    """Render a validation failure as one short line safe to classify."""
    first = error.errors()[0] if error.errors() else {}
    parts = [str(p) for p in first.get('loc', ())
             if not any(t in str(p).lower() for t in _FAILURE_CLASS_TRIGGERS)]
    where = '.'.join(parts)
    msg = str(first.get('msg', error)).replace('Value error, ', '')
    return f'{where}: {msg}' if where else msg


# ── The fleet, and its token ─────────────────────────────────────────────────

def provider_agent_ids(provider_name, *, deps: Collaborators):
    """Real Letta IDs of every LETTA_AGENTS entry tagged with this llm_provider."""
    ids = []
    for cfg in deps.agents:
        if cfg.get('llm_provider') == provider_name:
            real_id = deps.get_letta_id(cfg)
            if real_id:
                ids.append(real_id)
    return ids


def fetch_provider_oauth_creds(provider_name):
    """Return (creds_dict, provider_type) for a Letta provider, or (None, type).

    On this self-hosted server /v1/providers/ returns api_key_enc as plaintext
    JSON holding the OAuth bundle ({'access_token', 'account_id', ...}) — the
    same token the Letta server spends when an agent talks to the model, so a
    probe using it always watches the account the fleet is actually on."""
    with urllib.request.urlopen(f'{LETTA_BASE_URL}/v1/providers/', timeout=10) as resp:
        providers = json.loads(resp.read().decode())
    for p in providers:
        if p.get('name') != provider_name:
            continue
        raw = p.get('api_key_enc') or p.get('api_key')
        if not raw:
            return None, p.get('provider_type')
        try:
            creds = json.loads(raw)
        except ValueError:
            creds = {'access_token': raw}
        return creds, p.get('provider_type')
    return None, None


# ── Reading a payload ────────────────────────────────────────────────────────

def codex_window_label(window, fallback):
    """Pure: name a usage window by its real duration. The payload identifies
    its windows only by position (primary/secondary), but carries the length in
    `limit_window_seconds` — and the positions do move: on 2026-08-19
    `primary_window` was a 7-day window with no secondary, so the tile read
    "5h window 100% used, resets in 13h 16m", which is impossible on its face
    and sent a reader looking for a bug that wasn't there."""
    secs = window.get('limit_window_seconds') if isinstance(window, dict) \
        else window.limit_window_seconds
    if not secs:
        return fallback
    hours = float(secs) / 3600
    if hours < 24:
        return f'{hours:g}h'
    days = round(hours / 24)
    return 'weekly' if days == 7 else f'{days}d'


def classify_codex_usage(usage):
    """Map a chatgpt.com/backend-api/wham/usage payload to the probe's
    {'ok', 'text'} contract. Error text starts with 'llm_rate_limit:' so
    classify_failure() labels it 'rate-limited' like the old LLM probe did.

    Raises UsagePayloadError on a payload that carries no verdict — see
    CodexUsage. The caller turns that into a loud probe failure, which is the
    whole point: "I no longer understand this body" must not read as "fine"."""
    try:
        rl = CodexUsage.model_validate(usage).rate_limit
    except ValidationError as e:
        raise UsagePayloadError(_shape_detail(e)) from e
    windows = []
    for w, wfallback in ((rl.primary_window, '5h'), (rl.secondary_window, 'weekly')):
        if w is not None:
            windows.append((codex_window_label(w, wfallback), w.used_percent,
                            _human_reset(w.reset_at) or '?'))
    maxed = [f'{lbl} window {pct:.0f}% used, resets {reset}'
             for lbl, pct, reset in windows if pct >= 100]
    if rl.limit_reached or maxed or not rl.allowed:
        return {'ok': False, 'text': f"llm_rate_limit: {'; '.join(maxed) or 'limit reached'}"}
    return {'ok': True, 'text': ' / '.join(f'{lbl} {pct:.0f}%' for lbl, pct, _ in windows)}


def classify_claude_usage(usage):
    """Map an api.anthropic.com/api/oauth/usage payload (same field contract as
    the Model Stats extractor: five_hour/seven_day utilization) to the probe's
    {'ok', 'text'} contract. Raises UsagePayloadError — see ClaudeUsage."""
    try:
        parsed = ClaudeUsage.model_validate(usage)
    except ValidationError as e:
        raise UsagePayloadError(_shape_detail(e)) from e
    windows = []
    for w, label in ((parsed.five_hour, '5h'), (parsed.seven_day, 'weekly')):
        if w is not None:
            windows.append((label, w.utilization, _human_reset(w.resets_at) or '?'))
    maxed = [f'{lbl} window {pct:.0f}% used, resets {reset}'
             for lbl, pct, reset in windows if pct >= 100]
    if maxed:
        return {'ok': False, 'text': f"llm_rate_limit: {'; '.join(maxed)}"}
    return {'ok': True, 'text': ' / '.join(f'{lbl} {pct:.0f}%' for lbl, pct, _ in windows)}


# ── Asking the vendor ────────────────────────────────────────────────────────

def probe_usage_endpoint(url, headers, classify, timeout=20):
    """Shared fetch half of the zero-token probes: GET a usage endpoint with the
    provider's token and classify the payload. 401 → auth error (the provider's
    token is what Letta itself would fail with); 429 → the account is already
    being throttled at the door.

    A payload the classifier refuses is reported as a plain failure whose text
    deliberately does NOT start with 'llm_rate_limit:' — a shape change is not
    a rate limit, and labelling it one would fire the failover swap over a
    renamed JSON key."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'}
        if e.code == 429:
            return {'ok': False, 'text': 'llm_rate_limit: usage API returned HTTP 429'}
        return {'ok': False, 'text': f'HTTP {e.code}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}
    try:
        return classify(payload)
    except UsagePayloadError as e:
        return {'ok': False, 'text': f'usage payload not understood: {e}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


def probe_codex_usage(creds, timeout=20):
    """Zero-token ChatGPT/Codex quota check via the wham/usage endpoint (the
    same one Model Stats reads, but with the PROVIDER's token, not ~/.codex)."""
    return probe_usage_endpoint(
        'https://chatgpt.com/backend-api/wham/usage',
        {'Authorization': 'Bearer ' + (creds.get('access_token') or ''),
         'ChatGPT-Account-Id': creds.get('account_id', ''),
         'OpenAI-Beta': 'codex-1', 'originator': 'codex_cli_rs', 'User-Agent': 'codex'},
        classify_codex_usage, timeout)


def probe_claude_usage(creds, timeout=20):
    """Zero-token Anthropic quota check. Registered for the anthropic provider
    types, which is what the Mazda fleet's claude-pro-max row is."""
    token = (creds.get('access_token')
             or (creds.get('claudeAiOauth') or {}).get('accessToken') or '')
    return probe_usage_endpoint(
        'https://api.anthropic.com/api/oauth/usage',
        {'Authorization': 'Bearer ' + token,
         'anthropic-beta': 'oauth-2025-04-20', 'User-Agent': 'claude-code/2.0.32'},
        classify_claude_usage, timeout)


# provider_type (from /v1/providers/) → zero-token usage probe. Add entries here
# to cover new provider types; a type with no entry is silently skipped rather
# than pinged with an LLM call.
PROVIDER_USAGE_PROBES = {
    'chatgpt_oauth': probe_codex_usage,
    'anthropic': probe_claude_usage,
    'anthropic_oauth': probe_claude_usage,
}
