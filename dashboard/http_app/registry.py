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

from .ports import ScannerPort


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


@dataclass(frozen=True)
class Ports:
    """Everything the route ladders are allowed to depend on.

    One field per *populated* port. Fields are added by the round that
    populates their port — an empty adapter for a port nobody calls yet would
    be thirteen objects built per request to answer no question. The reserved
    names and their worklists live in `ports.py`.
    """

    scanner: ScannerPort


def current_ports() -> Ports:
    """Build the port bundle for this call. Never cache the result."""
    return Ports(scanner=_ServerScannerPort())
