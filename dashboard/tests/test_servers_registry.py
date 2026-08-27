"""`ServerSpec`, and the mistyped-entry failures it makes unexpressible.

Round 13 of the server.py refactor (Registry). `SERVERS` was 159 lines of dict
literal driving fifteen Server Management tiles across three machines.

The golden test here does what plan rule 9 asks for literally: it evaluates the
**old literal, out of git**, side by side with the derived view, against this
box's real live values. That is stronger than a pasted copy — the git object is
immutable, so the comparison cannot rot into a restatement of the new code, and
it stays honest about the four values (`PORT`, the Letta URL, and two log paths)
that differ per machine.
"""

from __future__ import annotations

import ast
import os
import subprocess

import pytest
from pydantic import ValidationError

import server
from hosts import LETTA_DOCKER_HOST
from servers import registry
from servers.registry import (
    CHECK_NAMES,
    HttpProbe,
    LogOnlyProbe,
    NamedCheckProbe,
    ServerSpec,
    TcpProbe,
    build_server_specs,
)

#: The commit round 13 started from — the last one whose server.py still
#: carried the SERVERS literal.
BASELINE_COMMIT = '75807d6b'

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _servers_literal_at_baseline() -> list[dict]:
    """The pre-refactor `SERVERS`, evaluated with this box's live values."""
    try:
        old_src = subprocess.run(
            ['git', 'show', f'{BASELINE_COMMIT}:dashboard/server.py'],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
        pytest.skip(f'git unavailable: {exc}')
    if old_src.returncode != 0:  # pragma: no cover
        pytest.skip(f'commit {BASELINE_COMMIT} not in this checkout')

    tree = ast.parse(old_src.stdout)
    node = next(
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and getattr(n.targets[0], 'id', '') == 'SERVERS')
    # The literal interpolates six names from server.py's own namespace.
    scope = {
        'os': os,
        'PORT': server.PORT,
        'LETTA_BASE_URL': server.LETTA_BASE_URL,
        'LETTA_DOCKER_HOST': LETTA_DOCKER_HOST,
        'LETTA_REMOTE_LOG_CACHE': server.LETTA_REMOTE_LOG_CACHE,
        'EXECUTOR_STARTUP_LOG': server.EXECUTOR_STARTUP_LOG,
        'LOGGER_API_STARTUP_LOG': server.LOGGER_API_STARTUP_LOG,
    }
    return eval(  # noqa: S307 — a literal out of our own git history
        compile(ast.Expression(node.value), '<baseline>', 'eval'), scope)


def _live_specs() -> tuple[ServerSpec, ...]:
    return build_server_specs(
        port=server.PORT,
        letta_base_url=server.LETTA_BASE_URL,
        letta_docker_host=LETTA_DOCKER_HOST,
        letta_remote_log_cache=server.LETTA_REMOTE_LOG_CACHE,
        executor_startup_log=server.EXECUTOR_STARTUP_LOG,
        logger_api_startup_log=server.LOGGER_API_STARTUP_LOG,
    )


def _spec(**overrides) -> dict:
    base = dict(key='executor', name='Executor Server', note='a note',
                probe=HttpProbe(health_url='http://127.0.0.1:8787/health'))
    base.update(overrides)
    return base


class TestGoldenParity:
    """Old literal and new derived view, side by side, on real live values."""

    def test_the_derived_view_matches_the_literal_exactly(self):
        assert server.SERVERS == _servers_literal_at_baseline()

    def test_every_entry_keeps_its_own_key_order(self):
        """`.get()` does not care, but a diff of two payloads does, and this is
        the cheapest place to notice the shape drifting."""
        for new, old in zip(server.SERVERS, _servers_literal_at_baseline()):
            assert list(new) == list(old), new['key']

    def test_the_tile_order_is_unchanged(self):
        assert ([s['key'] for s in server.SERVERS]
                == [s['key'] for s in _servers_literal_at_baseline()])

    def test_the_view_is_derived_not_a_second_copy(self):
        assert server.SERVERS == registry.as_configs(server.SERVER_SPECS)

    def test_the_api_servers_payload_is_unchanged(self):
        """What the browser actually reads. `skills` has never been set on any
        entry and still defaults to []; the model does not add it."""
        for cfg, old in zip(server.SERVERS, _servers_literal_at_baseline()):
            assert {
                'key': cfg['key'], 'name': cfg['name'],
                'note': cfg.get('note', ''), 'url': cfg.get('health_url'),
                'health_url': cfg.get('health_url'),
                'skills': cfg.get('skills', []),
            } == {
                'key': old['key'], 'name': old['name'],
                'note': old.get('note', ''), 'url': old.get('health_url'),
                'health_url': old.get('health_url'),
                'skills': old.get('skills', []),
            }


class TestOneActiveProbePerServer:
    """The shape that mattered most, and the defect it retires."""

    def test_every_live_server_declares_exactly_one_probe(self):
        for cfg in server.SERVERS:
            declared = [k for k in ('check', 'health_url', 'tcp_check')
                        if cfg.get(k)]
            assert len(declared) <= 1, f"{cfg['key']} declares {declared}"

    def test_an_entry_cannot_carry_both_a_check_and_a_health_url(self):
        """The old dict allowed it and `server_health()` resolves `check`
        first, so the health URL was configured, published by /api/servers as
        the tile's `url`, and never once pinged."""
        with pytest.raises(ValidationError):
            ServerSpec(**_spec(probe={
                'kind': 'check', 'check': 'win10_node_health',
                'health_url': 'http://127.0.0.1:8787/health'}))

    def test_a_log_only_server_must_have_a_log(self):
        with pytest.raises(ValidationError, match='off grey'):
            ServerSpec(**_spec(probe=LogOnlyProbe(), log_file=None))

    def test_a_log_only_server_with_a_log_is_fine(self):
        spec = ServerSpec(**_spec(probe=LogOnlyProbe(), log_file='/tmp/x.log'))
        assert spec.as_config() == {
            'key': 'executor', 'name': 'Executor Server',
            'log_file': '/tmp/x.log', 'note': 'a note'}

    def test_every_live_server_has_some_monitorable_source(self):
        """The invariant tests/test_server.py already asserted, now structural:
        a spec with no probe and no log is not constructible."""
        for cfg in server.SERVERS:
            assert (cfg.get('log_file') or cfg.get('health_url')
                    or cfg.get('tcp_check') or cfg.get('check')), cfg['key']


class TestNamedChecksAreAVocabularyNotAString:
    def test_check_names_and_health_checks_agree_in_both_directions(self):
        """One destination, one definition. A name in HEALTH_CHECKS that
        `CheckName` does not list is unreachable config; a name in `CheckName`
        that HEALTH_CHECKS does not define renders 'unknown check: ...' as a
        red tile's status text."""
        assert set(CHECK_NAMES) == set(server.HEALTH_CHECKS)

    def test_every_named_check_resolves_to_a_callable(self):
        for name in CHECK_NAMES:
            assert callable(server.HEALTH_CHECKS[name])

    def test_a_mistyped_check_name_is_refused(self):
        """Reachable today: `server_health()` answers
        `{'ok': False, 'text': 'unknown check: <name>'}` for a name it cannot
        resolve — a permanently red tile that reads like a dead service."""
        assert server.server_health({'check': 'win10_node_heath'}) == {
            'ok': False, 'text': 'unknown check: win10_node_heath'}
        with pytest.raises(ValidationError):
            NamedCheckProbe(check='win10_node_heath')


class TestTheOtherFieldsThatFailQuietly:
    def test_a_health_url_that_is_not_a_url_is_refused(self):
        with pytest.raises(ValidationError, match='not an http'):
            HttpProbe(health_url='127.0.0.1:8787/health')

    def test_a_relative_log_path_is_refused(self):
        """The tail runs from an unspecified cwd, so a relative path reads
        nothing and the tile just goes stale — indistinguishable from a
        service that stopped writing."""
        with pytest.raises(ValidationError, match='must be absolute'):
            ServerSpec(**_spec(log_file='tmp/executor.log'))

    def test_a_port_outside_the_tcp_range_is_refused(self):
        with pytest.raises(ValidationError, match='not a TCP port'):
            TcpProbe(host='127.0.0.1', port=87890)

    def test_a_port_given_as_a_string_is_not_coerced(self):
        with pytest.raises(ValidationError):
            TcpProbe(host='127.0.0.1', port='8789')

    def test_a_blank_note_is_refused(self):
        """A tile whose note is empty tells the operator nothing about what
        red means, and /api/servers happily serves ''."""
        with pytest.raises(ValidationError, match='must not be blank'):
            ServerSpec(**_spec(note='  '))

    def test_a_misspelled_field_is_refused_rather_than_ignored(self):
        with pytest.raises(ValidationError):
            ServerSpec(**_spec(win10docker=True))


class TestCrossEntryInvariants:
    def test_the_live_registry_hangs_together(self):
        registry._check_the_registry_hangs_together(_live_specs())

    def test_every_depends_on_names_a_real_server(self):
        keys = {s['key'] for s in server.SERVERS}
        for cfg in server.SERVERS:
            dep = cfg.get('depends_on')
            assert dep is None or dep in keys, cfg['key']

    def test_a_dangling_depends_on_is_refused(self):
        """Its root-cause line would point at a tile that does not exist."""
        specs = _live_specs() + (
            ServerSpec(**_spec(key='ghost', name='Ghost',
                               depends_on='win10-nod')),)
        with pytest.raises(ValueError, match='which is not a server'):
            registry._check_the_registry_hangs_together(specs)

    def test_a_self_dependency_is_refused(self):
        specs = (ServerSpec(**_spec(key='ghost', depends_on='ghost')),)
        with pytest.raises(ValueError, match='depends on itself'):
            registry._check_the_registry_hangs_together(specs)

    def test_a_duplicate_key_is_refused(self):
        specs = _live_specs() + (_live_specs()[0],)
        with pytest.raises(ValueError, match='duplicate server key'):
            registry._check_the_registry_hangs_together(specs)

    def test_a_duplicate_name_is_refused(self):
        """Two tiles labelled the same is a Restart button the operator cannot
        tell apart from its neighbour."""
        specs = _live_specs() + (
            ServerSpec(**_spec(key='executor-2', name='Executor Server')),)
        with pytest.raises(ValueError, match='duplicate server name'):
            registry._check_the_registry_hangs_together(specs)


class TestTheFactoryTakesItsValuesFromTheCompositionRoot:
    def test_the_port_reaches_the_dashboard_tile(self):
        specs = build_server_specs(
            port=9999, letta_base_url='http://letta.test',
            letta_docker_host='host', letta_remote_log_cache='/tmp/a.log',
            executor_startup_log='/tmp/b.log',
            logger_api_startup_log='/tmp/c.log')
        dashboard = next(s for s in specs if s.key == 'dashboard')
        assert dashboard.probe.health_url == 'http://localhost:9999/'

    def test_the_letta_url_reaches_both_the_probe_and_the_note(self):
        specs = build_server_specs(
            port=8765, letta_base_url='http://letta.test',
            letta_docker_host='box', letta_remote_log_cache='/tmp/a.log',
            executor_startup_log='/tmp/b.log',
            logger_api_startup_log='/tmp/c.log')
        letta = next(s for s in specs if s.key == 'letta')
        assert letta.probe.health_url == 'http://letta.test/v1/health/'
        assert 'http://letta.test' in letta.note
        assert 'box' in letta.note

    def test_server_wires_the_real_values(self):
        """Production wires the real collaborators (plan rule 4)."""
        dashboard = next(s for s in server.SERVER_SPECS if s.key == 'dashboard')
        assert dashboard.probe.health_url == f'http://localhost:{server.PORT}/'
        letta = next(s for s in server.SERVER_SPECS if s.key == 'letta')
        assert letta.log_file == server.LETTA_REMOTE_LOG_CACHE
        executor = next(s for s in server.SERVER_SPECS if s.key == 'executor')
        assert executor.log_file == server.EXECUTOR_STARTUP_LOG


class TestSpecsAreFrozen:
    def test_a_spec_cannot_be_mutated_in_flight(self):
        with pytest.raises(ValidationError):
            server.SERVER_SPECS[0].name = 'other'
