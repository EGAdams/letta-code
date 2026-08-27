"""The agent roster, the cards, the voice catalogue — and the duplicate tile.

Round 13 of the server.py refactor (Registry). Golden parity is done the way
`tests/test_servers_registry.py` does it: against the literals as they stood in
git at the baseline commit, so the comparison cannot decay into a restatement
of the module under test.

The roster is the one place in this round where the model **fixed** a live
defect rather than defending a fallback (plan rule 11). See
`TestTheDuplicateShelia`.
"""

from __future__ import annotations

import ast
import subprocess

import pytest
from pydantic import ValidationError

import server
from agents import registry as ar
from agents.registry import (
    LETTA_AGENT_SPECS,
    AgentCard,
    LettaAgentSpec,
    VoiceOption,
)
from tests.test_servers_registry import BASELINE_COMMIT, REPO_ROOT


def _literal_at_baseline(name: str):
    """A module-level literal out of the pre-round-13 server.py."""
    try:
        old = subprocess.run(
            ['git', 'show', f'{BASELINE_COMMIT}:dashboard/server.py'],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        pytest.skip(f'git unavailable: {exc}')
    if old.returncode != 0:  # pragma: no cover
        pytest.skip(f'commit {BASELINE_COMMIT} not in this checkout')

    tree = ast.parse(old.stdout)
    scope: dict = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = getattr(node.targets[0], 'id', '')
        if target in ('_MINION_TOOLS', '_MAZDA_TOOLS', 'CHATGPT_PLUS_PRO',
                      'CLAUDE_PRO_MAX', name):
            scope[target] = eval(  # noqa: S307 — our own git history
                compile(ast.Expression(node.value), '<baseline>', 'eval'),
                dict(scope))
    return scope[name]


def _agent(**overrides) -> dict:
    base = dict(name='Toyota', id='agent-38cf768e-e1eb-4c29-978a-c6bb64282d25')
    base.update(overrides)
    return base


def _card(**overrides) -> dict:
    base = dict(identity='Hailey', role='Support agent.',
                responsibilities=('Assist',), tools=('Letta messaging',),
                memory_summary='Retains project context.')
    base.update(overrides)
    return base


class TestTheDuplicateShelia:
    """The live defect this round fixed.

    `LETTA_AGENTS` listed Shelia twice. It is a list, so `build_agent_list()`
    appended both and `/api/agents` served 21 entries for 20 agents — two
    identical Shelia tiles on Agent Management, confirmed against the live
    dashboard on 2026-08-26 before the fix.

    `AGENT_CARDS` had the same duplicate as a repeated dict key, which Python
    resolves silently in favour of the last one. That is why the card text
    looked correct and hid the roster bug: the visible surface was fine and the
    iterated surface was not.
    """

    def test_the_baseline_literal_really_did_list_shelia_twice(self):
        old = _literal_at_baseline('LETTA_AGENTS')
        names = [a['name'] for a in old]
        assert names.count('Shelia') == 2, (
            'the defect this test documents is not in the baseline — check '
            'BASELINE_COMMIT')
        assert len(old) == 20

    def test_the_roster_now_lists_each_agent_once(self):
        names = [a['name'] for a in server.LETTA_AGENTS]
        assert len(names) == len(set(names))
        assert names.count('Shelia') == 1
        assert len(server.LETTA_AGENTS) == 19

    def test_the_agents_payload_has_one_tile_per_agent(self, monkeypatch):
        """What the browser reads. Stub the Letta lookup so this stays offline."""
        monkeypatch.setattr(server, 'get_letta_id', lambda cfg: cfg['id'])
        monkeypatch.setattr(server, '_agent_list_cache', {'value': None, 'ts': 0.0})
        names = [a['name'] for a in server.build_agent_list(force_refresh=True)]
        assert len(names) == len(set(names)), f'duplicate tile in {names}'
        assert names.count('Shelia') == 1

    def test_the_roster_is_otherwise_byte_identical_to_the_baseline(self):
        """Exactly one intended difference: the repeated entry is gone."""
        old = _literal_at_baseline('LETTA_AGENTS')
        seen, deduped = set(), []
        for cfg in old:
            if cfg['name'] in seen:
                continue
            seen.add(cfg['name'])
            deduped.append(cfg)
        assert server.LETTA_AGENTS == deduped

    def test_a_repeated_name_is_now_refused(self):
        with pytest.raises(ValueError, match='listed more than once'):
            ar._check_the_roster_hangs_together(
                LETTA_AGENT_SPECS + (LETTA_AGENT_SPECS[0],))

    def test_a_repeated_letta_id_is_now_refused(self):
        """Two names pointing at one agent: both tiles drive the same agent,
        and every fleet sweep does its work twice."""
        clone = LettaAgentSpec(**_agent(name='Toyota II'))
        with pytest.raises(ValueError, match='share a Letta id'):
            ar._check_the_roster_hangs_together(LETTA_AGENT_SPECS + (clone,))

    def test_an_agent_awaiting_discovery_does_not_count_as_a_clash(self):
        """`id=None` means "look me up by name"; several such entries are fine."""
        ar._check_the_roster_hangs_together((
            LettaAgentSpec(name='Jeri', id=None),
            LettaAgentSpec(name='Kelly', id=None),
        ))


class TestGoldenParity:
    def test_the_cards_are_unchanged(self):
        assert server.AGENT_CARDS == _literal_at_baseline('AGENT_CARDS')

    def test_the_card_order_is_unchanged(self):
        assert (list(server.AGENT_CARDS)
                == list(_literal_at_baseline('AGENT_CARDS')))

    def test_each_card_keeps_its_key_order(self):
        old = _literal_at_baseline('AGENT_CARDS')
        for name, card in server.AGENT_CARDS.items():
            assert list(card) == list(old[name]), name

    def test_the_voice_catalogue_is_unchanged(self):
        assert (server.AGENT_VOICE_OPTIONS
                == _literal_at_baseline('AGENT_VOICE_OPTIONS'))

    def test_the_provider_names_are_unchanged(self):
        assert server.CHATGPT_PLUS_PRO == 'chatgpt-plus-pro'
        assert server.CLAUDE_PRO_MAX == 'claude-pro-max'

    def test_the_views_are_derived_not_second_copies(self):
        assert server.LETTA_AGENTS == [s.as_config() for s in LETTA_AGENT_SPECS]
        assert server.AGENT_CARDS == {
            n: c.as_config() for n, c in ar.AGENT_CARD_SPECS.items()}
        assert server.AGENT_VOICE_OPTIONS == [
            v.voice_id for v in ar.VOICE_OPTION_SPECS]

    def test_build_agent_card_still_answers_for_every_carded_agent(self):
        for name in server.AGENT_CARDS:
            card = server.build_agent_card(name, 'agent-x')
            assert card['name'] == name
            assert card['agent_id'] == 'agent-x'
            assert card['role']


class TestARosterEntryThatWouldFail404:
    def test_a_malformed_letta_id_is_refused(self):
        """`get_letta_id()` hands a configured id straight through, and
        `build_agent_list()` only falls back to `unknown-<name>` when the id is
        falsy — so a typo'd id renders a normal tile whose every call 404s."""
        with pytest.raises(ValidationError, match='not a Letta agent id'):
            LettaAgentSpec(**_agent(id='38cf768e-e1eb-4c29-978a-c6bb64282d25'))

    def test_every_live_id_is_well_formed(self):
        for spec in LETTA_AGENT_SPECS:
            assert spec.id is None or spec.id.startswith('agent-')

    def test_none_is_still_allowed_and_means_discover_by_name(self):
        assert LettaAgentSpec(**_agent(id=None)).id is None
        assert ar.by_name('Jeri').id is None

    def test_a_blank_name_is_refused(self):
        with pytest.raises(ValidationError, match='must not be blank'):
            LettaAgentSpec(**_agent(name='  '))

    def test_a_misspelled_flag_is_refused_rather_than_silently_off(self):
        """`{'orchestror': True}` used to be an agent that simply was not a
        fleet lead, with no error anywhere."""
        with pytest.raises(ValidationError):
            LettaAgentSpec(**_agent(orchestror=True))

    def test_the_fleet_flags_still_read_the_same(self):
        mazda = next(c for c in server.LETTA_AGENTS if c['name'] == 'Mazda')
        assert mazda['orchestrator'] is True
        assert mazda['llm_provider'] == server.CLAUDE_PRO_MAX
        assert mazda['required_tools'] == [
            'record_trace', 'propose_improvement', 'run_experiment',
            'itemize_existing_expense']
        frita = next(c for c in server.LETTA_AGENTS if c['name'] == 'Frita')
        assert frita['uses_claude_sdk'] is True

    def test_an_agent_with_no_flags_carries_no_flag_keys(self):
        """Absence still means absence — `.get()` answers None as before."""
        toyota = next(c for c in server.LETTA_AGENTS if c['name'] == 'Toyota')
        assert toyota == {
            'name': 'Toyota', 'id': 'agent-38cf768e-e1eb-4c29-978a-c6bb64282d25'}


class TestACardThatWouldRenderBlank:
    def test_a_card_missing_a_field_is_refused(self):
        bad = _card()
        del bad['memory_summary']
        with pytest.raises(ValidationError):
            AgentCard(**bad)

    def test_a_blank_role_is_refused(self):
        with pytest.raises(ValidationError, match='must not be blank'):
            AgentCard(**_card(role='   '))

    def test_a_blank_bullet_is_refused(self):
        with pytest.raises(ValidationError, match='blank bullet'):
            AgentCard(**_card(responsibilities=('Assist', '  ')))

    def test_every_live_card_is_complete(self):
        for name, card in server.AGENT_CARDS.items():
            assert set(card) == {'identity', 'role', 'responsibilities',
                                 'tools', 'memory_summary'}, name
            assert card['responsibilities'] and card['tools'], name


class TestAVoiceThatWouldFailOnABackgroundThread:
    def test_every_live_voice_is_a_well_formed_edge_tts_id(self):
        for voice in server.AGENT_VOICE_OPTIONS:
            VoiceOption(voice_id=voice)

    def test_a_voice_that_is_not_an_edge_tts_id_is_refused(self):
        with pytest.raises(ValidationError, match='not an edge-tts voice id'):
            VoiceOption(voice_id='Aria')

    def test_a_voice_missing_the_neural_suffix_is_refused(self):
        with pytest.raises(ValidationError, match='not an edge-tts voice id'):
            VoiceOption(voice_id='en-US-Aria')

    def test_the_catalogue_is_still_the_membership_test_for_saving(self):
        """`set_agent_voice` rejects anything outside the catalogue, which is
        what keeps a bad id off the background thread in the first place."""
        assert 'en-US-AriaNeural' in server.AGENT_VOICE_OPTIONS
        assert 'Aria' not in server.AGENT_VOICE_OPTIONS


class TestTheVoiceConfigDrift:
    """Recorded, not fixed — and pinned so it cannot widen.

    `voice/config.py`'s `KNOWN_AGENT_NAMES` says it is "kept in sync with
    LETTA_AGENTS in server.py". It is not. It feeds the whisper prompt and the
    cleanup model's mishear correction, so editing it changes what the voice
    pipeline hears; that is a behaviour change and does not belong in a
    config-typing commit (plan rule 15). Round 13 hands this on.

    If you fix the drift, these tests are where you say so: empty both frozensets
    in `agents/registry.py` and the assertions below start requiring agreement.
    """

    def test_the_drift_is_exactly_what_the_registry_records(self):
        from voice.config import KNOWN_AGENT_NAMES

        roster = {s.name for s in LETTA_AGENT_SPECS}
        voice = set(KNOWN_AGENT_NAMES)
        assert roster - voice == ar.ROSTER_NAMES_MISSING_FROM_VOICE_CONFIG
        assert voice - roster == ar.VOICE_CONFIG_NAMES_NOT_ON_THE_ROSTER

    def test_the_receptionist_is_the_agent_missing_a_mishear_correction(self):
        """Toyota is the receptionist `/api/receptionist-agent` resolves, so it
        is the one name the voice path most needs whisper to get right."""
        assert 'Toyota' in ar.ROSTER_NAMES_MISSING_FROM_VOICE_CONFIG
        assert ar.by_name('Toyota') is not None


class TestSpecsAreFrozen:
    def test_a_roster_entry_cannot_be_mutated_in_flight(self):
        with pytest.raises(ValidationError):
            LETTA_AGENT_SPECS[0].name = 'other'

    def test_a_card_cannot_be_mutated_in_flight(self):
        with pytest.raises(ValidationError):
            ar.AGENT_CARD_SPECS['Scissari'].role = 'other'


class TestByName:
    def test_it_finds_a_roster_entry(self):
        assert ar.by_name('Mazda').orchestrator is True

    def test_it_strips(self):
        assert ar.by_name('  Frita  ').uses_claude_sdk is True

    def test_an_unknown_name_is_none(self):
        assert ar.by_name('Kelly') is None
