"""The restart registry: a key and its handler, as one fact.

Round 13 of the server.py refactor (Command). `server.py` carried
`RESTART_HANDLERS`, a 23-line dict of key → callable, and then
`RESTARTABLE_KEYS = set(RESTART_HANDLERS)` beside it. The two could not
disagree, but nothing tied either of them to `SERVERS`, and that is where the
gap was: a tile whose key nobody registered renders with no Restart button, and
the promise this dashboard is built on — "the user never needs the command
line" — quietly stops holding for that one service.

The handlers themselves stay in `server.py`; they are behaviour bound to that
module's own state, and moving them is round 23's job. What moves here is the
shape: a `RestartCommand` pairs a key with the callable that services it, and
`RestartRegistry` is the one place that knows a key is dispatchable — including
the check that every Server Management tile has a command.

Extra keys are legal, deliberately
----------------------------------
`chatgpt-provider` has a handler and no tile: its tile was commented out on
2026-08-19 but the swap-to-standby-token handler was kept. So the registry
requires *coverage* of the tiles, not equality with them, and says so rather
than leaving the asymmetry to be rediscovered.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pydantic import ConfigDict, field_validator

from contracts import StrictModel


class RestartCommand(StrictModel):
    """One Server Management Restart button.

    `key` and `handler` are one fact, not two. Previously the key was a dict
    key and membership was a second derived set; a command with no handler was
    not expressible, but neither was it possible to say *what* the registry
    should cover.
    """

    # Callables are not a Pydantic-strict type, so this model relaxes exactly
    # one thing: arbitrary attribute types. It stays frozen and extra-forbidding.
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              arbitrary_types_allowed=True)

    key: str
    handler: Callable[[], dict]
    note: str = ''

    @field_validator('key')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('handler')
    @classmethod
    def _is_callable(cls, value: Callable[[], dict]) -> Callable[[], dict]:
        if not callable(value):
            raise ValueError(
                'a non-callable handler makes the Restart button report '
                '"restart <key> error" for every press')
        return value


class RestartRegistry:
    """Every restartable key, and the one place a restart is dispatched."""

    def __init__(self, commands: Iterable[RestartCommand]):
        self._commands: tuple[RestartCommand, ...] = tuple(commands)
        keys = [c.key for c in self._commands]
        if len(set(keys)) != len(keys):
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            raise ValueError(
                f'two restart commands share a key: {dupes} — the later one '
                'wins silently and the earlier handler is dead code')
        self._by_key = {c.key: c for c in self._commands}

    @property
    def keys(self) -> frozenset[str]:
        """What `RESTARTABLE_KEYS` was: which tiles get a Restart button."""
        return frozenset(self._by_key)

    def handler_for(self, key: str) -> Callable[[], dict] | None:
        command = self._by_key.get(key)
        return command.handler if command else None

    def as_handler_map(self) -> dict:
        """The legacy `RESTART_HANDLERS` dict view. Derived, so it cannot drift."""
        return {c.key: c.handler for c in self._commands}

    def dispatch(self, key: str) -> dict:
        """Run `key`'s restart. Returns `{ok, text}`; never raises.

        A handler that raises becomes `{'ok': False, ...}` rather than a 500,
        because the caller is a button on a page and the operator needs to be
        told, not shown a stack trace.
        """
        handler = self.handler_for(key)
        if handler is None:
            return {'ok': False, 'text': f'No restart handler for "{key}".'}
        try:
            return handler()
        except Exception as exc:  # noqa: BLE001 — a button must always answer
            return {'ok': False, 'text': f'restart {key} error: {exc}'}

    def check_covers(self, server_keys: Iterable[str]) -> None:
        """Every Server Management tile must have a Restart button.

        The dashboard's standing promise is that the user never needs the
        command line. A tile with no command renders without the button, which
        looks like a deliberate design choice rather than a missing
        registration.

        The converse is allowed: `chatgpt-provider` keeps its handler with its
        tile commented out. An extra key is inert, a missing one is a service
        the operator cannot restart.
        """
        missing = sorted(set(server_keys) - self.keys)
        if missing:
            raise ValueError(
                f'Server Management tiles with no restart command: {missing} — '
                'each renders without a Restart button')
