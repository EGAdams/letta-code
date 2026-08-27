"""The Server Management registry, typed and built by a factory.

`server.py` carried this as 159 lines of dict literal. The tiles it drives are
the operator's only view of fifteen services on three machines, and every field
in it is a string with nothing checking it. The failure signature the round-6
postscript exists to warn about is sitting right here: a mistyped `check` name
or systemd unit gives a Restart button that reports success and does nothing,
or a tile that can never be anything but grey.

Two shapes, deliberately
------------------------
`ServerSpec` is not a flat model with everything optional. How a server is
*actively* probed is a genuine discriminated union — exactly one of a named
check function, an HTTP health URL, or a TCP connect — and "no active probe at
all" is a fourth case, not a missing field. Tailing a log file is independent of
all four: the `letta` entry both pings an HTTP endpoint and tails a log that an
SSH loop pulls into `/tmp`.

Writing that as one flat model would let `{'health_url': ..., 'check': ...}`
through, and `server_health()` resolves `check` first — so the health URL would
be configured, displayed by `/api/servers`, and never actually pinged.

Why a factory and not a literal
-------------------------------
Four of these entries interpolate values `server.py` computes: the dashboard's
own `PORT`, two startup-log paths, and the local cache the Letta log-pull loop
writes to. Those belong to the composition root, so `build_servers()` takes
them as arguments rather than importing `server` back. `server.py` calls it
once, which is what a composition root is for.
"""

from __future__ import annotations

import os
from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from contracts import StrictModel

# The named check functions a spec may reference. This is the *vocabulary*;
# `server.py`'s HEALTH_CHECKS dict binds each name to a callable, and
# `tests/test_servers_registry.py` asserts the two agree in both directions.
#
# One destination, one definition (plan rule 5): a spec naming a check that
# HEALTH_CHECKS does not define used to render "unknown check: <name>" as the
# tile's status text — a red server that is actually a typo.
CheckName = Literal[
    'frita_executor_health',
    'win10_node_health',
    'document_vision_health',
    'chatgpt_provider_health',
    'mazda_categorizer_fallback_health',
]

CHECK_NAMES: tuple[str, ...] = (
    'frita_executor_health',
    'win10_node_health',
    'document_vision_health',
    'chatgpt_provider_health',
    'mazda_categorizer_fallback_health',
)


class NamedCheckProbe(StrictModel):
    """A body-aware probe in `HEALTH_CHECKS` — when "HTTP 200" is not enough."""

    kind: Literal['check'] = 'check'
    check: CheckName


class HttpProbe(StrictModel):
    """An HTTP endpoint whose 200 means the service is up."""

    kind: Literal['health_url'] = 'health_url'
    health_url: str

    @field_validator('health_url')
    @classmethod
    def _is_an_http_url(cls, value: str) -> str:
        if not value.startswith(('http://', 'https://')):
            raise ValueError(
                f'{value!r} is not an http(s) URL — the probe would fail for '
                'the wrong reason and the tile would read as a dead service')
        return value


class TcpProbe(StrictModel):
    """A bare TCP connect, for MCP proxies with no HTTP response to parse."""

    kind: Literal['tcp'] = 'tcp'
    host: str
    port: int

    @field_validator('port')
    @classmethod
    def _is_a_real_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError(f'{value} is not a TCP port')
        return value

    @field_validator('host')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value


class LogOnlyProbe(StrictModel):
    """No endpoint to ping: status comes from whether the log is still moving.

    Its own case rather than an absent field, because `log_file` then stops
    being optional — a log-only server with no log has nothing to derive a
    status from and renders permanently grey.
    """

    kind: Literal['log_only'] = 'log_only'


ServerProbe = Annotated[
    Union[NamedCheckProbe, HttpProbe, TcpProbe, LogOnlyProbe],
    Field(discriminator='kind'),
]


class ServerSpec(StrictModel):
    """One Server Management tile.

    Required, and why:

    * `key` — the id every restart, log and health call is addressed by.
    * `name` — the tile's label.
    * `note` — the operator's only explanation of what a red tile *means*.
      `/api/servers` defaults it to `''`, which renders a tile nobody can act
      on; all fifteen entries have written one, so requiring it keeps that true.
    * `probe` — how this server is checked. See the module docstring.

    Optional, and why:

    * `log_file` — independent of the probe, except for `LogOnlyProbe` where it
      becomes required.
    * `remote` / `win10_docker` — presentation and container-state flags that
      default off; absent means "local", which is the safe reading.
    * `depends_on` — root-cause ordering. Absent means "nothing upstream",
      which is exactly what the UI does with a missing value.
    """

    key: str
    name: str
    note: str
    probe: ServerProbe
    log_file: str | None = None
    remote: bool = False
    win10_docker: bool = False
    depends_on: str | None = None

    @field_validator('key', 'name', 'note')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('log_file')
    @classmethod
    def _is_an_absolute_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith('/'):
            raise ValueError(
                f'{value!r} must be absolute — the log tail runs from an '
                'unspecified working directory, so a relative path silently '
                'reads nothing and the tile goes stale')
        return value

    @model_validator(mode='after')
    def _a_log_only_server_has_a_log(self) -> ServerSpec:
        if self.probe.kind == 'log_only' and not self.log_file:
            raise ValueError(
                f'{self.key!r} has no active probe and no log_file, so nothing '
                'can ever move its tile off grey')
        return self

    def as_config(self) -> dict:
        """The flat legacy dict `server.py` and `monitoring/` still pass around.

        Only the keys the original entry carried are emitted, so `.get('check')`
        and `.get('health_url')` keep answering `None` exactly as before.
        """
        cfg: dict = {'key': self.key, 'name': self.name}
        if isinstance(self.probe, NamedCheckProbe):
            cfg['check'] = self.probe.check
        elif isinstance(self.probe, HttpProbe):
            cfg['health_url'] = self.probe.health_url
        elif isinstance(self.probe, TcpProbe):
            cfg['tcp_check'] = (self.probe.host, self.probe.port)
        if self.log_file is not None:
            cfg['log_file'] = self.log_file
        if self.remote:
            cfg['remote'] = True
        if self.win10_docker:
            cfg['win10_docker'] = True
        if self.depends_on is not None:
            cfg['depends_on'] = self.depends_on
        cfg['note'] = self.note
        return cfg


def build_server_specs(
    *,
    port: int,
    letta_base_url: str,
    letta_docker_host: str,
    letta_remote_log_cache: str,
    executor_startup_log: str,
    logger_api_startup_log: str,
) -> tuple[ServerSpec, ...]:
    """The fifteen tiles, wired to the composition root's values.

    Order is the Server Management tab's display order, `win10-node` first
    because it is the root-cause indicator everything else hangs off.
    """
    specs = (
        ServerSpec(
            key='win10-node',
            name='Win10 WSL Node',
            probe=NamedCheckProbe(check='win10_node_health'),
            remote=True,
            note='The Win10 WSL host (100.80.49.10) that runs Letta, the Frita SDK '
                 'executor, and the Logger API. ROOT CAUSE indicator: if this is red, '
                 'those are all symptoms — fix the node first (Restart revives '
                 'tailscaled via the Windows host).',
        ),
        # Letta has a log_file despite running remotely: _letta_remote_log_pull_loop
        # SSHes every 30s and content-sniffs *-json.log for Letta's signature.
        # docker-proxy on that box has repeatedly forwarded :8283 to an untracked
        # orphaned containerd task while the docker-ps-visible `letta-server` sits
        # idle, so `docker logs letta-server` would show the wrong (dead-quiet)
        # process. Do not assume the named container is the live one.
        ServerSpec(
            key='letta',
            name='Letta Server',
            probe=HttpProbe(health_url=f'{letta_base_url}/v1/health/'),
            log_file=letta_remote_log_cache,
            remote=True,
            win10_docker=True,
            depends_on='win10-node',
            note=f'Letta API ({letta_base_url}) — logs pulled periodically over SSH '
                 f'from {letta_docker_host} (Docker container on the Win10 box)',
        ),
        # DISABLED 2026-08-19 (EG): the ChatGPT Provider tile is retired from Server
        # Management. It watched the chatgpt-plus-pro OAuth credential and went red
        # when that token died or its weekly allowance ran out. Models are now chosen
        # per agent on the Agent Management pages, so a single provider-wide tile no
        # longer describes anything the user acts on — and its name was stale besides
        # (Mazda's fleet moved to claude-pro-max on 2026-08-16).
        #
        # Commented out rather than deleted in case it was covering a case we forgot.
        # Nothing else was removed: chatgpt_provider_health(), the account-swap panel
        # on Model Stats, and _chatgpt_provider_poll_loop() (which flags fleet agents
        # red on Agent Management) all still run. Uncomment to bring the tile back —
        # and note its restart handler is still registered, which is why
        # RESTARTABLE_KEYS is deliberately allowed to be a superset of these keys.
        # ServerSpec(
        #     key='chatgpt-provider',
        #     name='ChatGPT Provider (Mazda LLM)',
        #     probe=NamedCheckProbe(check='chatgpt_provider_health'),
        #     remote=True,
        #     depends_on='letta',
        #     note='OAuth token on the chatgpt-plus-pro Letta provider — the credential '
        #          'Mazda + the Suzuki fleet make every LLM call with. RED = token dead '
        #          '(e.g. expired access token + invalid refresh token): every dispatch '
        #          'to the fleet fails with HTTP 401 even while scans and all other '
        #          'servers look fine. Restart swaps in the standby account token '
        #          '(swap_chatgpt_provider_token.sh on the Letta box).',
        # ),
        ServerSpec(
            key='executor',
            name='Executor Server',
            probe=HttpProbe(health_url='http://127.0.0.1:8787/health'),
            log_file=executor_startup_log,
            note='executor_run REST backend — runs locally on this machine (:8787)',
        ),
        ServerSpec(
            key='browser-server',
            name='ChatGPT Browser Server',
            probe=HttpProbe(health_url='http://100.80.49.10:5001/health'),
            remote=True,
            depends_on='win10-node',
            note='Browser automation server for relay_message_to_chatgpt tool — '
                 'controls a logged-in ChatGPT browser session on the Win10 box '
                 '(:5001). RED = not running or Chrome not logged into chatgpt.com. '
                 'See dashboard/BROWSER_SERVER_INTEGRATION.md.',
        ),
        ServerSpec(
            key='mcp-proxy',
            name='MCP Executor Bridge',
            probe=TcpProbe(host='127.0.0.1', port=8789),
            note='mcp-proxy stdio bridge for executor_run MCP tool (:8789) — '
                 'if this dies Scissari/Codex executor_run silently fails',
        ),
        ServerSpec(
            key='dashboard',
            name='Dashboard Server',
            probe=HttpProbe(health_url=f'http://localhost:{port}/'),
            log_file='/tmp/dashboard_8765.log',
            note='This dashboard (server.py)',
        ),
        ServerSpec(
            key='dashboard-proxy',
            name='Dashboard Proxy (Win10)',
            probe=HttpProbe(health_url='http://100.80.49.10:8765/'),
            remote=True,
            depends_on='win10-node',
            note='WSL TCP proxy on the Win10 box (100.80.49.10:8765) that relays to '
                 'this dashboard so the Win10-side browser can reach it via '
                 'http://localhost:8765 without the (offline) Win10 Tailscale node. '
                 'If this is red, http://localhost:8765 on the Win10 machine will '
                 'not load.',
        ),
        # The bare root has no index file (DocumentRoot serves a directory with no
        # index.php) — Apache 403s there even when the API is fully healthy, so the
        # health check would never flip green. Hit a real PHP+MySQL+Apache-rewrite
        # endpoint instead (the one the smoke test in [[reference_logger_api_ops]]
        # uses) — 200 means the whole stack works.
        ServerSpec(
            key='logger-api',
            name='Logger API',
            probe=HttpProbe(health_url=(
                'http://100.80.49.10:8284/libraries/local-php-api/object/select'
                '?object_view_id=OrchestratorAgent_2026')),
            log_file=logger_api_startup_log,
            remote=True,
            win10_docker=True,
            depends_on='win10-node',
            note='Docker logger API (live agent log viewer) — mysql + php-api '
                 'containers on the Win10 box, started over SSH (see Start button)',
        ),
        ServerSpec(
            key='lettabot',
            name='Lettabot (Telegram)',
            probe=HttpProbe(health_url='http://localhost:8091/health'),
            log_file=os.path.expanduser('~/lettabot/cron-log.jsonl'),
            note='Scissari Telegram bot — internal API :8091; '
                 'heartbeat/cron log at ~/lettabot/cron-log.jsonl '
                 '(stdout goes to systemd journal: '
                 '`journalctl --user -u lettabot -f`)',
        ),
        ServerSpec(
            key='thought-bridge',
            name='Thought Bridge',
            probe=HttpProbe(health_url='http://localhost:8899/'),
            note='lettabot → browser live thought stream '
                 '(monitor :8899, WS bridge :8766)',
        ),
        ServerSpec(
            key='frita-executor',
            name='Frita Executor (Win10)',
            probe=NamedCheckProbe(check='frita_executor_health'),
            remote=True,
            win10_docker=True,
            depends_on='win10-node',
            note="Frita's win10_run + Claude-SDK runner. Verifies the SDK-capable "
                 'executor on host :8799 (what the Mazda minions reach) AND watches '
                 'for a stale no-SDK "ghost" executor on :8797 (the recurring '
                 'duplicate-stack bug). Restart via "Start" button.',
        ),
        ServerSpec(
            key='mazda-tools-mcp',
            name='Mazda Tools MCP',
            probe=TcpProbe(host='127.0.0.1', port=8791),
            note="mcp-proxy for Mazda's Letta tools (mazda-tools-mcp.service, :8791) "
                 "— if down, Mazda's tool calls silently fail",
        ),
        ServerSpec(
            key='document-vision',
            name='Document Vision (Scan Classify)',
            probe=NamedCheckProbe(check='document_vision_health'),
            note="classify_scan.py's 3-tier fallback (Gemini -> ChatGPT-OAuth/Codex "
                 'CLI -> OpenAI key) that lets Mazda classify/read a scanned '
                 'document. RED here (all 3 tiers down) means '
                 'process_scanned_document() refuses to dispatch Mazda at all — see '
                 'DOCUMENT_VISION_HALT_MESSAGE.',
        ),
        ServerSpec(
            key='mazda-categorizer-llm',
            name='LLM Provider Fallbacks (Categorizer)',
            probe=NamedCheckProbe(check='mazda_categorizer_fallback_health'),
            note="tools/categorizer/categorizer_main.py's vendor->category LLM chain "
                 "(gemini -> chatgpt-oauth [EG's account, then mom's] -> anthropic), "
                 'read from real call outcomes in ~/.mazda/provider_health.json — '
                 'never a synthetic probe. YELLOW = a fallback fired recently (still '
                 'working, worth a look). RED = every tracked tier failed on its last '
                 'attempt. Built 2026-07-20 after the gemini CLI broke silently for '
                 '3+ days.',
        ),
    )
    _check_the_registry_hangs_together(specs)
    return specs


def _check_the_registry_hangs_together(specs: tuple[ServerSpec, ...]) -> None:
    """Cross-entry invariants no single spec can check for itself."""
    keys = [s.key for s in specs]
    if len(set(keys)) != len(keys):
        raise ValueError(f'duplicate server key in {keys}')
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ValueError(f'duplicate server name in {names}')
    known = set(keys)
    for spec in specs:
        if spec.depends_on is not None and spec.depends_on not in known:
            raise ValueError(
                f'{spec.key!r} depends_on {spec.depends_on!r}, which is not a '
                'server — its root-cause line would point at nothing')
        if spec.depends_on == spec.key:
            raise ValueError(f'{spec.key!r} depends on itself')


def as_configs(specs: tuple[ServerSpec, ...]) -> list[dict]:
    """The legacy `SERVERS` list-of-dicts view. Derived, so it cannot drift."""
    return [s.as_config() for s in specs]
