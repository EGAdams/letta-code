"""Which object satisfies each port, resolved per call.

`current_ports()` is the one place the HTTP layer is allowed to know that
`server` exists. A route asks for a port; this module decides what answers it.

Late binding is not optional
----------------------------
`server` is resolved out of `sys.modules` on every call, and a fresh `Ports`
bundle is built on every call, for the same reason `http_app/services.py` uses
a module `__getattr__`: `server.py` imports `http_app` from its own tail, so a
module-scope `import server` in a route mixin is a cycle, and — more
importantly — the whole test suite monkeypatches `server.<name>` and expects
the routes to see it. Cache the bundle at import and every one of those
monkeypatches starts lying while still looking exactly like it works.

`tests/test_http_app_ports.py` pins that behaviour. Do not "optimise" it.

Adapters, and how they retire
-----------------------------
`_ServerScannerPort` reads its collaborators off the `server` module by name,
which is still a service locator — but a service locator confined to one file
with eight known names in it, instead of one spread across two 600-line route
ladders with ~170. When round 22 moves the scanner hardware into its own
module, this adapter is what changes: the routes do not.
"""
import importlib
import os
import sys
from dataclasses import dataclass
from typing import Optional

from .ports import AgentsPort, ReportsPort, ScannerPort, ServersPort


def _server():
    """The live `server` module. Never captured — see the module docstring."""
    return sys.modules.get('server') or importlib.import_module('server')


class _ServerScannerPort:
    """`ScannerPort` backed by the scanner names still living in server.py.

    Every attribute is fetched at call time rather than bound in `__init__`,
    so `monkeypatch.setattr(server, 'run_scanner', ...)` is honoured even by a
    port instance that was constructed before the patch.
    """

    @property
    def image_url_prefix(self) -> str:
        return _server().SCANNER_IMAGE_URL_PREFIX

    def image_path(self, key: str) -> Optional[str]:
        # Round 13 moved `SCANNERS` to hardware/scanners.py, where it is now a
        # derived view of typed `ScannerSpec`s. This adapter is where that would
        # have been felt — and it is the whole argument for round 12 that only
        # this file could feel it, because the route asks "where is this
        # scanner's image?" and never learned that a spec is a dict.
        #
        # It kept the dict read rather than switching to the spec: ~10 tests
        # monkeypatch `server.SCANNERS` with plain dicts to drive unknown and
        # misconfigured scanners, and reading the typed specs directly would
        # make those patches stop landing while still looking green. Round 22
        # owns that switch, along with the call sites in server.py.
        module = _server()
        spec = module.SCANNERS.get(key)
        if not spec:
            return None
        output = spec.get('output')
        if not output:
            return None
        return os.path.join(module.SCAN_TOOLS_DIR, output)

    def status(self, key: str) -> dict:
        return _server().scanner_status(key)

    def diagnostics(self, key: str) -> dict:
        return _server().scanner_diagnostics(key)

    def run(self, key: str) -> dict:
        return _server().run_scanner(key)

    def clear_verification_lock(self, key: str) -> dict:
        return _server().clear_scanner_verification_lock(key)

    def fix_printer(self) -> dict:
        return _server().fix_deskjet_printer()


class _ServerReportsPort:
    """`ReportsPort`'s round-13 half: the month tabs and the report cards.

    Everything is read off `server` at call time, not bound in `__init__` —
    ~15 tests drive the report paths by monkeypatching
    `server.ROL_FINANCE_REPORTS` / `server.ROL_FINANCES_REPORTS_MONTHS`, and a
    port that captured the registry module's own globals instead would ignore
    every one of them while looking exactly like it worked.
    """

    @property
    def url_prefix(self) -> str:
        return _server().ROL_FINANCES_REPORTS_URL_PREFIX

    def resolve_month_key(self, requested: Optional[str]) -> str:
        module = _server()
        months = module.ROL_FINANCES_REPORTS_MONTHS
        default = module.ROL_FINANCES_REPORTS_DEFAULT_MONTH
        return requested if requested in months else default

    def cards_for_month(self, month_key: str) -> list:
        return _server()._rol_finance_reports_for_month(month_key)


class _ServerServersPort:
    """`ServersPort`'s round-13 half: the registry the tab is drawn from."""

    def all(self) -> list:
        return _server().SERVERS

    def restartable_keys(self) -> frozenset:
        return frozenset(_server().RESTARTABLE_KEYS)


class _ServerAgentsPort:
    """`AgentsPort`'s round-13 half: resolving the receptionist."""

    #: Toyota is the receptionist the voice path routes through. The name is
    #: the roster key, so it lives with the code that looks it up rather than
    #: being spelled again in a route.
    RECEPTIONIST_NAME = 'Toyota'

    def receptionist(self) -> Optional[dict]:
        module = _server()
        cfg = next((a for a in module.LETTA_AGENTS
                    if a['name'] == self.RECEPTIONIST_NAME), None)
        if cfg is None:
            return None
        agent_id = module.get_letta_id(cfg)
        if not agent_id:
            return None
        return {'name': self.RECEPTIONIST_NAME, 'agent_id': agent_id}


@dataclass(frozen=True)
class Ports:
    """Everything the route ladders are allowed to depend on.

    One field per *populated* port. Fields are added by the round that
    populates their port — an empty adapter for a port nobody calls yet would
    be thirteen objects built per request to answer no question. The reserved
    names and their worklists live in `ports.py`.
    """

    scanner: ScannerPort
    reports: ReportsPort
    servers: ServersPort
    agents: AgentsPort


def current_ports() -> Ports:
    """Build the port bundle for this call. Never cache the result."""
    return Ports(
        scanner=_ServerScannerPort(),
        reports=_ServerReportsPort(),
        servers=_ServerServersPort(),
        agents=_ServerAgentsPort(),
    )
