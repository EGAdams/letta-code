"""The typed seams between the route ladders and the rest of the dashboard.

Why this file exists
--------------------
`http_app/services.py` exposes `srv`, a PEP 562 module `__getattr__` onto
`server`. It is a Service Locator: the two route ladders reach through it for
~170 free names, 26 of them private. That shape has one specific, recurring
cost — moving a function out of `server.py` does not remove the name from
`server.py`, because the route still says `srv.the_name`, so the name stays
behind as an import. Roughly 90 lines of `server.py` are re-exports that exist
for no other reason, and they never expire, because their caller is the one
thing that is not moving.

A port is the fix. The routes depend on a small, named interface — the part
they actually use — and something else decides which object satisfies it.
Moving code then costs a line in the adapter, not a permanent name in
`server.py`.

Protocols, not ABCs
-------------------
The implementations are plain modules and plain objects. `Protocol` checks them
structurally, so nothing has to inherit anything, and a later round can swap a
module-backed adapter for a real service class without touching a route.
`@runtime_checkable` is deliberately *not* applied: `isinstance` against a
Protocol only checks method *names*, which is a weaker assertion than the
wiring tests in `tests/test_http_app_ports.py` already make.

Population is per round
-----------------------
`ScannerPort` is populated: round 12 converted it end to end as the worked
example. The other thirteen are declared, with the names each one will absorb
listed in its docstring, and are filled in by the round that moves their code
(see the burn-down in `notes_plans_handoffs/dashboard_refactor_plan.html`).
A declared-but-empty Protocol is not an abstraction yet — it is a reserved
name and a worklist. Do not add a fifteenth port: a grab-bag `MiscPort` is
`srv` with a new name.
"""
from typing import Optional, Protocol


class ScannerPort(Protocol):
    """The two HP scanners and the DeskJet queue repair.

    Round 12's worked example, chosen because it is small, self-contained, and
    a tab you can watch work. Absorbs eight `srv` names:

        SCANNERS, SCAN_TOOLS_DIR, SCANNER_IMAGE_URL_PREFIX, run_scanner,
        scanner_status, scanner_diagnostics, clear_scanner_verification_lock,
        fix_deskjet_printer

    Note what happened to the first three. `SCANNERS` and `SCAN_TOOLS_DIR` were
    reached by exactly one route, which joined them to answer one question:
    *where is this scanner's last image?* That is `image_path()`. The route no
    longer knows that a scanner spec is a dict with an `output` key, so
    round 13 can turn it into a `ScannerSpec` model without touching a route.
    """

    @property
    def image_url_prefix(self) -> str:
        """The GET path that serves a scanner's most recent image.

        Config the ladder matches on, not behaviour — it stays a value.
        """

    def image_path(self, key: str) -> Optional[str]:
        """Where `key`'s last scan was written, or None for an unknown scanner.

        Returns the configured path whether or not a file is there yet;
        deciding what a missing file means is the route's business (a 404).
        """

    def status(self, key: str) -> dict:
        """Observation only. Never starts WIA, never writes an image."""

    def diagnostics(self, key: str) -> dict:
        """The scanner-diagnostics tab's payload for one scanner."""

    def run(self, key: str) -> dict:
        """Start a manual scan. Dispatches intake in a background thread."""

    def clear_verification_lock(self, key: str) -> dict:
        """Terminal-out a stuck intake lock without touching finance data."""

    def fix_printer(self) -> dict:
        """The DeskJet queue repair. No scanner key: there is only one."""


# ── declared, not yet populated ─────────────────────────────────────────────
# Each of these is filled in by the round that moves its code. The counts are
# how many of the ~170 `srv` names the port absorbs, measured at 054a3650.


class ReportsPort(Protocol):
    """24 names. Report discovery, path aliasing, status classification, the
    month and receipt-only queries, and the three HTML builders. The biggest
    port, and the one most likely to want splitting once round 16 has moved
    the HTML out. Rounds 16, 20 and 25 populate the rest.

    Round 13 took the four config names off the ladder. Note what happened to
    them, because it is the same lesson `ScannerPort` taught: the ladder was
    joining `ROL_FINANCES_REPORTS_MONTHS` and
    `ROL_FINANCES_REPORTS_DEFAULT_MONTH` to answer one question — *which month
    tab is this request looking at?* That is `resolve_month_key()`, and the
    route no longer knows the months are a dict.
    """

    @property
    def url_prefix(self) -> str:
        """The URL path the statement reports are served under.

        Config the ladder matches paths against, not behaviour — a value, the
        same way `ScannerPort.image_url_prefix` is.
        """

    def resolve_month_key(self, requested: Optional[str]) -> str:
        """The month tab `requested` names, or the default if it names none.

        Never raises and never returns an unknown key: an unrecognised month
        falls back to the default tab, which is what the ladder did inline.
        """

    def cards_for_month(self, month_key: str) -> list:
        """The statement report cards shown on `month_key`'s tab.

        All-year cards live only under the default (January) tab, which is the
        dashboard's all-year view.
        """


class AgentsPort(Protocol):
    """23 names. Roster, cards, voices, models, OAuth accounts, activity,
    health, headless runs. Round 24 populates the rest — it is only tractable
    after round 14 replaces the six hand-rolled caches underneath it.

    Round 13 took `LETTA_AGENTS` off the ladder. The one route that read it was
    scanning the roster for Toyota and then resolving its id: one question,
    `receptionist()`.
    """

    def receptionist(self) -> Optional[dict]:
        """`{'name', 'agent_id'}` for the receptionist, or None if unresolved.

        None covers both "not on the roster" and "on the roster but its Letta
        id could not be resolved" — the route answers the same error for both,
        so the port does not distinguish them.
        """


class ModelStatsPort(Protocol):
    """16 names. Stats sources, mute overlay, Codex sync, ChatGPT provider
    accounts. Populated by round 24."""


class ServersPort(Protocol):
    """14 names. The Server Management tab: status, logs, restart, deploy.
    Round 23 populates the rest — the behaviour that reads the registry.

    Round 13 moved `SERVERS` out to `servers/registry.py` as typed
    `ServerSpec`s and took it, and `RESTARTABLE_KEYS`, off the ladder.
    """

    def all(self) -> list:
        """Every Server Management entry, in tab order.

        Still the legacy flat dicts: `servers/registry.py` derives them from
        the specs, and round 23 is what turns the ladder's readers into
        something that asks the spec directly.
        """

    def restartable_keys(self) -> frozenset:
        """Which entries have a Restart button.

        A frozenset, not the registry: the ladder only ever asks whether one
        key is in it.
        """


class MonitoringPort(Protocol):
    """12 names. PC metrics, the SSH roster, Win10 containers, failure
    classification. Every name behind it already lives in `monitoring/`, so
    this port is nearly free — round 12 already pointed the routes at those
    modules directly."""


class DocumentPort(Protocol):
    """11 names. Receipt lookup, supporting documents, presence checks, Excel
    render. Populated by rounds 19 and 20."""


class ExpensePort(Protocol):
    """10 names. Manual entry, stored-expense edit and search, notes.
    Populated by round 21."""


class IntakePort(Protocol):
    """9 names. The recent-intake record, the halt file, scanner intake
    lookups. Populated by round 15."""


class PipelinePort(Protocol):
    """8 names. Document processing, statement break-up, Mazda fill,
    reprocess. Populated by rounds 17 and 18."""


class VoiceNotesPort(Protocol):
    """8 names. Voice upload, speech synthesis, the receptionist strategy,
    note commands. Round 12 pointed the routes at `voice/` directly; the port
    is populated when a round gives the voice pipeline a composition root."""


class TerminalPort(Protocol):
    """6 names. PTY spawn and reap, WebSocket framing — mostly
    `terminal/pty_session.py` and `http_app/websocket.py` already. Round 12
    pointed `terminal_ws.py` at both directly."""


class CategoryPort(Protocol):
    """5 names. Recategorize, undo, vendor review. Already behind
    `finance/recategorize.py`."""


class MazdaPort(Protocol):
    """2 names. The mode switch. Round 11 reduced it to two verbs — it is the
    shape the other thirteen are aiming at."""
