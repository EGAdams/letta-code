"""The agent roster, the Agent Card copy, and the voice catalogue — typed.

Round 13 of the server.py refactor (Registry). Three literals lived in
`server.py`: `LETTA_AGENTS` (the roster `/api/agents` renders and every fleet
sweep iterates), `AGENT_CARDS` (the per-agent card text), and
`AGENT_VOICE_OPTIONS` (the edge-tts voices the dropdown offers).

They were a list of dicts, a dict of dicts, and a list of strings, with nothing
checking any of them. Two live defects were sitting in them when this round
started:

* **`LETTA_AGENTS` listed Shelia twice**, identically. It is a *list*, so
  `build_agent_list()` appended both and `/api/agents` served 21 tiles for 20
  agents — two identical Shelia cards in Agent Management, verified against the
  live dashboard on 2026-08-26. `AGENT_CARDS` had the same duplicate as a
  repeated dict key, where Python silently kept the last one, so the card text
  looked fine and hid the roster bug.
* `voice/config.py`'s `KNOWN_AGENT_NAMES` claims to be "kept in sync with
  LETTA_AGENTS" and is not — see `ROSTER_NAMES_MISSING_FROM_VOICE_CONFIG`.

The duplicate is **fixed** here (plan rule 11: this one is a fix, not a
defence). The voice drift is recorded, not fixed — changing the whisper prompt
is a voice-pipeline behaviour change and does not belong in a config-typing
commit.
"""

from __future__ import annotations

from pydantic import field_validator

from contracts import StrictModel


class LettaAgentSpec(StrictModel):
    """One agent on the roster.

    Required:

    * `name` — the dashboard's handle for the agent, and the key
      `get_letta_id()` auto-discovers by when `id` is None.
    * `id` — the real Letta agent id, or `None` to auto-discover by name.
      `None` is a meaningful value, not an omission, so it is declared rather
      than defaulted: an entry that forgot to say which agent it is would
      otherwise silently become a name lookup against the live API.

    Optional, each because its absence has a defined meaning:

    * `uses_claude_sdk` — off means "not an SDK runner", which is the
      overwhelmingly common case.
    * `required_tools` — empty means "nothing to provision-check". An agent
      with no declared tools is not flagged unprovisioned, which is correct for
      the agents that have none.
    * `llm_provider` — `None` means "not part of a provider-wide sweep"; the
      quota probes skip it rather than guessing a provider.
    * `orchestrator` — off means "not a fleet lead".
    """

    name: str
    id: str | None
    uses_claude_sdk: bool = False
    required_tools: tuple[str, ...] = ()
    llm_provider: str | None = None
    orchestrator: bool = False

    @field_validator('name')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('id')
    @classmethod
    def _looks_like_a_letta_id(cls, value: str | None) -> str | None:
        """A malformed id is not a lookup failure, it is a 404 on every call.

        `get_letta_id()` returns a configured id straight through without
        checking it, and `build_agent_list()` only falls back to
        `unknown-<name>` when the id is falsy — so a typo'd id renders a normal
        tile whose every message call 404s.
        """
        if value is None:
            return value
        if not value.startswith('agent-'):
            raise ValueError(
                f'{value!r} is not a Letta agent id (agent-<uuid>); it would '
                'render as a working tile whose calls all 404')
        return value

    def as_config(self) -> dict:
        """The legacy dict shape, carrying only the keys the entry declared.

        `.get('required_tools')`, `.get('llm_provider')` and
        `.get('orchestrator')` are all read for truthiness, so emitting the
        defaults would be harmless — but omitting them keeps the payload
        byte-identical to the literal this replaced.
        """
        cfg: dict = {'name': self.name, 'id': self.id}
        if self.uses_claude_sdk:
            cfg['uses_claude_sdk'] = True
        if self.required_tools:
            cfg['required_tools'] = list(self.required_tools)
        if self.llm_provider is not None:
            cfg['llm_provider'] = self.llm_provider
        if self.orchestrator:
            cfg['orchestrator'] = True
        return cfg


class AgentCard(StrictModel):
    """The Agent Card tab's copy for one agent.

    Every field is required. The old dict's failure was a card missing a key
    rendering as a blank panel rather than an error — `build_agent_card()`
    substitutes a whole placeholder card for an *unknown* agent, but a known
    agent with a half-filled entry got the half.
    """

    identity: str
    role: str
    responsibilities: tuple[str, ...]
    tools: tuple[str, ...]
    memory_summary: str

    @field_validator('identity', 'role', 'memory_summary')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('responsibilities', 'tools')
    @classmethod
    def _no_blank_entries(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError('a blank bullet renders as an empty list item')
        return value

    def as_config(self) -> dict:
        return {
            'identity': self.identity,
            'role': self.role,
            'responsibilities': list(self.responsibilities),
            'tools': list(self.tools),
            'memory_summary': self.memory_summary,
        }


class VoiceOption(StrictModel):
    """One edge-tts voice id offered by the Input Options dropdown.

    A wrong id does not fail when it is picked — it fails later, at speech
    time, on a background thread, where nobody sees it. `agent_voice_payload()`
    and the save path both check membership of the catalogue, so the catalogue
    itself is the only place the shape can be validated.
    """

    voice_id: str

    @field_validator('voice_id')
    @classmethod
    def _is_an_edge_tts_id(cls, value: str) -> str:
        parts = value.split('-')
        if len(parts) < 3 or not value.endswith('Neural'):
            raise ValueError(
                f'{value!r} is not an edge-tts voice id '
                '(<lang>-<REGION>-<Name>Neural) — it would fail at speech '
                'time on a background thread, not when it is chosen')
        return value


# ── The roster ────────────────────────────────────────────────────────────────
# Add a new Letta agent here. `id=None` auto-discovers by name from the Letta
# agent list (cached 5 min via AGENT_LIST_CACHE_TTL; bypass with ?refresh=1).

MINION_TOOLS: tuple[str, ...] = ('run_claude_code_sdk',)

# Mazda's health is signalled by her self-improvement MCP tools (served by
# mazda-tools-mcp.service on :8791) — they attach/detach together, so requiring
# a few core ones cleanly flags an unprovisioned Mazda (e.g. the MCP server
# down) without flapping. NOTE: do NOT require relay_message_to_chatgpt — that
# is a browser-relay tool from a discarded design; this incarnation of Mazda
# does not carry it (verified live: her tools are record_trace /
# propose_improvement / run_experiment / judge_trace / gate_check /
# activate_wrapper / rollback_wrapper / load_wrapper_revision /
# propose_memory_note / verify_statement_totals).
MAZDA_TOOLS: tuple[str, ...] = (
    'record_trace',
    'propose_improvement',
    'run_experiment',
    'itemize_existing_expense',
)

# Suzuki + her 6 minions run on the same chatgpt-plus-pro OAuth account, so a
# ChatGPT/Codex rate limit (HTTP 429 from chatgpt.com/backend-api/codex/responses)
# hits all of them simultaneously — see the mazda_chatgpt_429_rate_limit_2026_06_18
# memory. _poll_chatgpt_provider_once() checks the provider's token once and
# propagates ok/error to every agent tagged with this provider, so no per-agent
# canary flag is needed for that to work.
CHATGPT_PLUS_PRO = 'chatgpt-plus-pro'

# BYOK provider backed by this box's (Rosemary46) Claude subscription OAuth
# token — never an ANTHROPIC_API_KEY. The provider row itself only holds a raw
# Bearer access token (no refresh_token handling server-side), so
# shell_scripts/sync_mazda_claude_token.sh re-pushes the current token from
# ~/.claude/.credentials.json hourly via cron on this box, the same way
# sync_frita_claude_token.sh keeps Frita's local credentials fresh — this box's
# own interactive `claude` CLI usage refreshes it and passes the WAF, where the
# Letta server's own refresh attempts do not. The whole Mazda fleet (Mazda + her
# 5 minions) runs on this provider; Suzuki's fleet remains on chatgpt-plus-pro.
CLAUDE_PRO_MAX = 'claude-pro-max'

LETTA_AGENT_SPECS: tuple[LettaAgentSpec, ...] = (
    LettaAgentSpec(name='Toyota', id='agent-38cf768e-e1eb-4c29-978a-c6bb64282d25'),
    LettaAgentSpec(name='Scissari', id='agent-5955b0c2-7922-4ffe-9e43-b116053b80fa'),
    LettaAgentSpec(name='Frita', id='agent-881a883f-edd0-4963-bf67-6ef178b8f018',
                   uses_claude_sdk=True),
    # Listed twice in the pre-round-13 literal; /api/agents served two identical
    # Shelia tiles as a result. Fixed by _check_the_roster_hangs_together below.
    LettaAgentSpec(name='Shelia', id='agent-1c2e170c-a67a-4364-b370-16a6b48c0770'),
    LettaAgentSpec(name='Hailey', id='agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03'),
    LettaAgentSpec(name='Jeri', id=None),
    LettaAgentSpec(name='Mazda', id='agent-6b536cf4-ec88-4290-b595-fed21d14bd8e',
                   required_tools=MAZDA_TOOLS, llm_provider=CLAUDE_PRO_MAX,
                   orchestrator=True),
    LettaAgentSpec(name='Mazda Router',
                   id='agent-bc561f63-a5bd-4192-806e-58d92593da2b',
                   required_tools=MINION_TOOLS, llm_provider=CLAUDE_PRO_MAX),
    LettaAgentSpec(name='Mazda Parser',
                   id='agent-a5063757-46c7-4054-a07d-2b1263db43a8',
                   required_tools=MINION_TOOLS, llm_provider=CLAUDE_PRO_MAX),
    LettaAgentSpec(name='Mazda Vendor Identity',
                   id='agent-acd624ac-17f2-4a74-aa34-78036cac4d66',
                   required_tools=MINION_TOOLS, llm_provider=CLAUDE_PRO_MAX),
    LettaAgentSpec(name='Mazda Receipt Linker',
                   id='agent-9a14f800-d848-4914-bfd4-53ab62bc177b',
                   required_tools=MINION_TOOLS, llm_provider=CLAUDE_PRO_MAX),
    LettaAgentSpec(name='Mazda Categorization',
                   id='agent-c429ff25-c8af-4f1a-a6f1-6d48307e2874',
                   required_tools=MINION_TOOLS, llm_provider=CLAUDE_PRO_MAX),
    LettaAgentSpec(name='Suzuki', id='agent-c4e58e29-8c06-4ca9-a18d-b8536442af13',
                   llm_provider=CHATGPT_PLUS_PRO, orchestrator=True),
    LettaAgentSpec(name='Suzuki Router',
                   id='agent-df4deb48-3a46-4fe4-887a-6aeb95ddc6d6',
                   llm_provider=CHATGPT_PLUS_PRO),
    LettaAgentSpec(name='Suzuki Reproducer',
                   id='agent-ad0c3e39-bd14-4f79-af95-140e4cf21325',
                   llm_provider=CHATGPT_PLUS_PRO),
    LettaAgentSpec(name='Suzuki Static Analysis',
                   id='agent-a820e191-bc39-413c-bb0c-6344d5b37643',
                   llm_provider=CHATGPT_PLUS_PRO),
    LettaAgentSpec(name='Suzuki Patch',
                   id='agent-2c585993-1193-42d8-9bf5-1805b426a0da',
                   llm_provider=CHATGPT_PLUS_PRO),
    LettaAgentSpec(name='Suzuki Test Runner',
                   id='agent-a90f1413-6599-4750-b7e0-ee5634984162',
                   llm_provider=CHATGPT_PLUS_PRO),
    LettaAgentSpec(name='Suzuki Regression',
                   id='agent-8af8fec4-5114-40b3-99ab-173edd35ebd2',
                   llm_provider=CHATGPT_PLUS_PRO),
)


def _check_the_roster_hangs_together(
        specs: tuple[LettaAgentSpec, ...]) -> None:
    """No agent listed twice, by name or by id.

    This is the check that was missing. `build_agent_list()` iterates the
    roster as a list, so a repeated entry is a repeated tile; the fleet sweeps
    (`agent_activity_status`, the provider quota probes, `agent_health`) each
    do the work twice for it.
    """
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(
            f'agent listed more than once in the roster: {dupes} — '
            '/api/agents would serve a duplicate tile for each')
    ids = [s.id for s in specs if s.id is not None]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f'two roster entries share a Letta id: {dupes}')


_check_the_roster_hangs_together(LETTA_AGENT_SPECS)


# ── The cards ─────────────────────────────────────────────────────────────────

AGENT_CARD_SPECS: dict[str, AgentCard] = {
    'Scissari': AgentCard(
        identity='Scissari',
        role='Lead coordination and execution agent focused on cross-agent '
             'orchestration, dashboard work, and operational follow-through.',
        responsibilities=(
            'Coordinate multi-agent tasks and user-facing follow-up',
            'Drive dashboard and observability improvements',
            'Track execution flow across agents and tools',
        ),
        tools=(
            'Letta agent messaging',
            'executor_run / host command execution',
            'dashboard inspection and API verification',
        ),
        memory_summary='Maintains durable project context and coordination '
                       'state so shared workflows stay consistent across '
                       'sessions.',
    ),
    'Frita': AgentCard(
        identity='Frita',
        role='Infrastructure and deployment agent for the Windows 10 dashboard '
             'host and public exposure path.',
        responsibilities=(
            'Publish and repair dashboard hosting on the Win10 machine',
            'Inspect live services, tunnels, and dashboard backends',
            'Deploy and verify dashboard/API fixes end-to-end',
        ),
        tools=(
            'win10_run',
            'cloudflared / tunnel operations',
            'host file and process inspection',
        ),
        memory_summary='Keeps operational knowledge about the Win10 dashboard '
                       'environment, serving paths, and tunnel setup.',
    ),
    'Shelia': AgentCard(
        identity='Shelia',
        role='Narrow, evidence-based Rosemary46 Windows/WSL/Tailscale recovery '
             'operator.',
        responsibilities=(
            'Inspect Rosemary46 host, WSL, keepalive-task, and Tailscale evidence',
            'Start the fixed WSL keepalive and restart tailscaled when evidence '
            'requires it',
            'Verify real Tailscale and SSH recovery without hiding dashboard '
            'failures',
        ),
        tools=(
            'shelia_status',
            'shelia_start_keepalive',
            'shelia_restart_tailscale',
            'shelia_reauth_instructions',
            'shelia_verify_recovery',
        ),
        memory_summary='Maintains a strict recovery sequence and reports '
                       'unreachable, authentication, WSL, and SSH failures '
                       'separately.',
    ),
    'Hailey': AgentCard(
        identity='Hailey',
        role='Support agent available for collaboration and delegated '
             'operational tasks.',
        responsibilities=(
            'Assist with shared task execution',
            'Provide agent-side support when routed work is assigned',
        ),
        tools=('Letta messaging and standard agent workflows',),
        memory_summary='Participates in the shared agent ecosystem with '
                       'retained project context when available.',
    ),
    'Jeri': AgentCard(
        identity='Jeri',
        role='Financial analyst agent focused on finance workflows, document '
             'interpretation, and structured operational guidance.',
        responsibilities=(
            'Support January and finance-analysis workflows',
            'Interpret financial material and process-related inputs',
            'Participate in A2A-oriented coordination flows',
        ),
        tools=(
            'A2A messaging patterns',
            'finance workflow guidance',
            'dashboard-driven visibility and control surfaces',
        ),
        memory_summary='Designed as a specialized analyst persona with '
                       'persistent behavioral and workflow guidance.',
    ),
    'Mazda': AgentCard(
        identity='Mazda',
        role='Self-improving engineering/operations agent focused on thoughtful '
             'execution and clearer agent self-description.',
        responsibilities=(
            'Execute assigned technical tasks',
            'Improve agent-facing structure and usability',
            'Help define clearer agent identity and card patterns',
        ),
        tools=(
            'Agent messaging',
            'technical execution workflows',
            'structured self-description patterns',
        ),
        memory_summary='Uses retained context to refine its own behavior and '
                       'improve the system around it over time.',
    ),
    'Claude': AgentCard(
        identity='Claude',
        role='External coding collaborator represented in the dashboard for '
             'shared visibility.',
        responsibilities=(
            'Contribute code-focused implementation and analysis',
            'Coordinate with the local agent ecosystem when integrated',
        ),
        tools=(
            'Code editing and analysis workflows',
            'shared dashboard visibility',
        ),
        memory_summary='Not a Letta-backed agent here, but included as a '
                       'visible collaborator in the dashboard ecosystem.',
    ),
    'Suzuki': AgentCard(
        identity='Suzuki',
        role='Self-improving software debugging orchestrator — triages bugs, '
             'delegates to specialist minions, verifies patches, and learns '
             'across runs.',
        responsibilities=(
            'Receive bug reports and run the 12-stage debug workflow',
            'Delegate triage, reproduction, static analysis, patching, test '
            'execution, and regression checking to specialist minions',
            'Record traces and propose wrapper improvements after each run',
        ),
        tools=(
            'DebugStageEnvelope handoff contract',
            'executor_run / host command execution',
            'self-improvement MCP tools (record_trace, propose_improvement, '
            'run_experiment)',
        ),
        memory_summary='Accumulates debugging lessons across runs via the '
                       'shared self-improvement kernel inherited from Mazda.',
    ),
}


# ── The voice catalogue ───────────────────────────────────────────────────────

VOICE_OPTION_SPECS: tuple[VoiceOption, ...] = tuple(
    VoiceOption(voice_id=v) for v in (
        'en-GB-SoniaNeural',
        'en-US-AnaNeural',
        'en-US-AriaNeural',
        'en-US-AvaNeural',
        'en-US-AvaMultilingualNeural',
        'en-US-EmmaNeural',
        'en-US-EmmaMultilingualNeural',
        'en-US-JennyNeural',
        'en-US-MichelleNeural',
        'en-US-AndrewNeural',
        'en-US-BrianNeural',
        'en-US-ChristopherNeural',
        'en-US-EricNeural',
        'en-US-GuyNeural',
        'en-US-RogerNeural',
        'en-US-SteffanNeural',
    )
)


# ── The legacy views ──────────────────────────────────────────────────────────
# Derived, so they cannot drift from the specs above.

LETTA_AGENTS: list[dict] = [s.as_config() for s in LETTA_AGENT_SPECS]
AGENT_CARDS: dict[str, dict] = {
    name: card.as_config() for name, card in AGENT_CARD_SPECS.items()
}
AGENT_VOICE_OPTIONS: list[str] = [v.voice_id for v in VOICE_OPTION_SPECS]


# Recorded, not fixed: `voice/config.py`'s KNOWN_AGENT_NAMES says it is "kept in
# sync with LETTA_AGENTS in server.py" and has drifted. It feeds the whisper
# prompt and the cleanup model's mishear correction, so changing it changes what
# the voice pipeline hears — a behaviour change that does not belong in a
# config-typing commit (plan rule 15: things that fail differently do not travel
# together). `tests/test_agents_registry.py` pins the exact drift so it cannot
# widen, and the round-13 report hands it on.
#
# Two divergences: the receptionist (Toyota) has no mishear correction at all,
# and one minion is spelled 'Suzuki Patch' on the roster but 'Suzuki Patcher' in
# the voice list — so a spoken "Suzuki Patcher" is corrected TO a name no agent
# answers to.
ROSTER_NAMES_MISSING_FROM_VOICE_CONFIG: frozenset[str] = frozenset(
    {'Toyota', 'Suzuki Patch'})
VOICE_CONFIG_NAMES_NOT_ON_THE_ROSTER: frozenset[str] = frozenset(
    {'Suzuki Patcher'})


def by_name(name: str) -> LettaAgentSpec | None:
    """The roster entry for `name`, or None."""
    wanted = str(name or '').strip()
    return next((s for s in LETTA_AGENT_SPECS if s.name == wanted), None)
