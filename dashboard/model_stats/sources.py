"""Which accounts the Model Stats tab reads, and what kind each one is.

A typed registry rather than a dict of dicts. The three fields are the whole
contract between this table and the reader -- `kind` selects the extractor,
`host` decides whether it runs here or over SSH -- and a typo in either used
to surface as a card that silently returned the bare `out` skeleton with no
windows and no error, because `_model_stats_uncached` falls through when it
recognises no kind. Pydantic turns that into an ImportError at boot.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Model Stats (per-OAuth/CLI session token usage) ───────────────────────────
# Catch token-exhaustion early: each source reports current session usage % +
# reset date. Codex (ChatGPT OAuth) exposes a rich `rate_limits` block (5h +
# weekly used_percent + resets_at) in its session rollouts; Claude exposes
# cumulative tokens/cost per model in ~/.claude/stats-cache.json (no weekly
# limit %); Gemini has no machine-readable limit, so it's account-only.
# W11 = this box (local); R46 = mom's machine (rosemary46) over SSH.
# Re-exported here under its historical name; the address itself lives in
# hosts.py, because the PC Monitor polls the same box.
from hosts import R46_SSH_HOST


class ModelStatSource(BaseModel):
    """One account whose token usage the dashboard reports.

    Frozen because the registry is process-wide shared state: a route handler
    that mutated a source would change what every later reading measures.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    label: str = Field(min_length=1)
    #: Selects the extractor program. Adding a kind here without teaching
    #: `_model_stats_uncached` about it yields a card with no windows, so the
    #: literal is the enforcement point.
    kind: Literal['codex', 'claude', 'gemini']
    #: None means "this box"; anything else is an ssh destination.
    host: Optional[str] = None


MODEL_STAT_SOURCES: dict[str, ModelStatSource] = {
    key: ModelStatSource(**cfg) for key, cfg in {
        'w11-codex':  {'label': 'eg1972 codex',     'kind': 'codex',  'host': None},
        'r46-codex':  {'label': 'rbarnesrol codex', 'kind': 'codex',  'host': R46_SSH_HOST},
        'w11-claude': {'label': 'eg1972 claude',    'kind': 'claude', 'host': None},
        'r46-claude': {'label': 'rbarnesrol claude','kind': 'claude', 'host': R46_SSH_HOST},
        # 2026-08-16: replaced Antigravity CLI monitoring with the Gemini API key
        # ("Gemini Flash Fill" button's engine) -- different Google products, see
        # _GEMINI_FLASH_FILL_EXTRACT_PY's docstring for why they were conflated.
        'gemini':     {'label': 'Gemini Flash', 'kind': 'gemini', 'host': None},
    }.items()
}
