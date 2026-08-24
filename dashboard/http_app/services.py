"""Late-bound handle on server.py's service layer.

The route mixins need ~180 names from server.py, but server.py imports *this*
package from its own tail, so a module-scope `import server` in a mixin is a
cycle: whichever side is imported first stalls the other half-built.

PEP 562 module `__getattr__` breaks it. `srv.foo` resolves at *call* time
against whatever `server` is in sys.modules — which is also why monkeypatching
`server.foo` in a test, or rebinding it at runtime, is still seen by the routes.
A plain `from server import foo` would have snapshotted it at import time.

Usage in a mixin:

    from . import services as srv
    ...
    srv.build_agent_list()
"""
import importlib as _importlib
import sys as _sys


def __getattr__(name):
    module = _sys.modules.get('server') or _importlib.import_module('server')
    try:
        return getattr(module, name)
    except AttributeError as exc:
        raise AttributeError(
            f'server.py defines no {name!r} — the HTTP layer expects it') from exc


def __dir__():
    module = _sys.modules.get('server')
    return sorted(dir(module)) if module else []
