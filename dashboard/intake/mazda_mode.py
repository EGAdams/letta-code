"""Automatic vs Semi-Automatic: who reads a freshly scanned document first.

Two names for a fork that already existed. ``MAZDA_DECISION_MODE`` has always
held ``'auto'`` or ``'human_only'``, and server.py has always branched on it in
exactly one place (``_dispatch_mazda_or_block``). Nothing about that branch
changes here.

What changes is who may move it, and when it is read:

* It used to be resolved once at process start, so switching Mazda back on
  meant editing a systemd unit and restarting the dashboard. Now the operator
  flips it from the intake dialog and the *next* scan obeys. Documents already
  dispatched are untouched either way -- a mode is a decision about the next
  document, never a retroactive one.
* The answer is persisted, so a restart does not silently hand the work back
  to whichever mode the environment happened to name.

The environment variable is still the default, and still the only thing that
decides the mode before anyone has ever touched the switch. It is supplied to
the service as a *callable* rather than a captured string precisely so it
stays the live default: server.py's ``EXECUTION_MODE`` remains the single
answer to "what does this box do out of the box", and the test suite keeps
monkeypatching it.

Naming, deliberately: the wire and the store speak ``auto``/``human_only``
because every existing record, test and status message already does. Only the
operator-facing *labels* are the new words. Renaming the values would have
meant rewriting intake history to say the same thing differently.

Models describe data, ABCs describe behavior (see contracts.py). The store is
an ABC so a test decides where the answer lives without touching this file and
without writing to the operator's real one.
"""

from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Callable, Literal, Optional, Union

from pydantic import ValidationError, field_validator

from contracts import StrictModel

#: Mazda is dispatched on every scan and files the document herself.
AUTOMATIC = 'auto'
#: Mazda is not dispatched; the document waits in the dialog for a human, who
#: can still run Mazda's own readers a page at a time via "Mazda Fill".
SEMI_AUTOMATIC = 'human_only'

#: What the switch says about the mode currently in force. The label is
#: computed here rather than in the browser so the two never disagree about
#: what "on" means -- the toggle reads its own text off the server's answer.
MAZDA_MODE_LABELS: dict[str, str] = {
    AUTOMATIC: 'Mazda Automatic',
    SEMI_AUTOMATIC: 'Mazda Semi-Automatic',
}


class MazdaModeRequest(StrictModel):
    """Body of POST /api/mazda-mode.

    A boolean, not a mode string: the control is a two-position switch, and a
    switch that can post an arbitrary word is a switch that can post a typo.
    ``automatic`` is also the only thing the browser actually knows -- it holds
    a checkbox, not an intake vocabulary.
    """

    automatic: bool

    @classmethod
    def from_http(cls, data) -> 'MazdaModeRequest':
        """Strictly a bool. Absent means False; anything else is rejected.

        Deliberately NOT ``bool(data.get('automatic'))``: that reads the string
        "maybe" -- or "false", or any other truthy junk a caller might send --
        as a request to switch Mazda ON, which is the one direction that costs
        money. StrictModel refuses a non-bool outright, so a malformed body
        leaves the switch exactly where it was and says why.
        """
        if not isinstance(data, dict):
            raise ValueError('request body must be an object')
        return cls.model_validate({'automatic': data.get('automatic', False)})

    @property
    def mode(self) -> str:
        return AUTOMATIC if self.automatic else SEMI_AUTOMATIC


class MazdaModeState(StrictModel):
    """The mode in force, as both sides need to see it.

    ``source`` distinguishes "nobody has ever touched the switch, this is what
    the environment says" from "an operator chose this". Only the second
    survives a change to the service file, and the dialog is the only place
    anyone would ever notice the difference.
    """

    ok: bool = True
    mode: Literal['auto', 'human_only']
    automatic: bool
    label: str
    source: Literal['operator', 'default']

    @field_validator('label')
    @classmethod
    def _label_must_be_known(cls, value: str) -> str:
        if value not in MAZDA_MODE_LABELS.values():
            raise ValueError(f'unknown mode label: {value!r}')
        return value

    def to_http(self) -> dict:
        return self.model_dump()


def state_for(mode: str, *, source: str) -> MazdaModeState:
    """Build the full state from the one value that decides it."""
    if mode not in MAZDA_MODE_LABELS:
        raise ValueError(f'unknown Mazda mode: {mode!r}')
    return MazdaModeState(
        mode=mode,
        automatic=(mode == AUTOMATIC),
        label=MAZDA_MODE_LABELS[mode],
        source=source,
    )


class IMazdaModeStore(ABC):
    """Where an operator's choice outlives the process."""

    @abstractmethod
    def read(self) -> Optional[str]:
        """The stored mode, or None if nobody has ever chosen one."""

    @abstractmethod
    def write(self, mode: str) -> None:
        """Record `mode` as the operator's standing choice."""


class JsonFileMazdaModeStore(IMazdaModeStore):
    """A one-key JSON file beside the other small operator preferences.

    Unreadable, missing or nonsense content all mean the same thing -- nobody
    has chosen -- so the environment default takes over rather than the intake
    pipeline failing over a preferences file. A corrupt file that silently
    turned Mazda on would be the expensive failure; falling back to the
    configured default cannot be worse than a fresh box.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()

    def read(self) -> Optional[str]:
        try:
            with open(self._path, encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        mode = data.get('mode') if isinstance(data, dict) else None
        return mode if mode in MAZDA_MODE_LABELS else None

    def write(self, mode: str) -> None:
        if mode not in MAZDA_MODE_LABELS:
            raise ValueError(f'unknown Mazda mode: {mode!r}')
        with self._lock:
            directory = os.path.dirname(self._path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp = f'{self._path}.tmp.{os.getpid()}'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump({'mode': mode}, fh)
            os.replace(tmp, self._path)


class InMemoryMazdaModeStore(IMazdaModeStore):
    """For tests and for a deployment that wants the env var to win every
    restart. Holds the choice for the life of the process and no longer."""

    def __init__(self, mode: Optional[str] = None):
        self._mode = mode

    def read(self) -> Optional[str]:
        return self._mode

    def write(self, mode: str) -> None:
        if mode not in MAZDA_MODE_LABELS:
            raise ValueError(f'unknown Mazda mode: {mode!r}')
        self._mode = mode


class MazdaModeService:
    """The one place that answers "is Mazda driving right now?".

    ``default_mode`` is accepted as either a string or a zero-argument callable.
    The callable form is what server.py passes, so ``EXECUTION_MODE`` stays the
    live default -- read at the moment the question is asked rather than
    captured when this object was built.
    """

    def __init__(self, store: IMazdaModeStore,
                 default_mode: Union[str, Callable[[], str]] = AUTOMATIC):
        self._store = store
        self._default_mode = default_mode

    def _default(self) -> str:
        raw = self._default_mode() if callable(self._default_mode) else self._default_mode
        return raw if raw in MAZDA_MODE_LABELS else AUTOMATIC

    def current(self) -> MazdaModeState:
        stored = self._store.read()
        if stored is None:
            return state_for(self._default(), source='default')
        return state_for(stored, source='operator')

    def mode(self) -> str:
        """Just the value ``_dispatch_mazda_or_block`` branches on."""
        return self.current().mode

    def set(self, request: MazdaModeRequest) -> MazdaModeState:
        self._store.write(request.mode)
        return state_for(request.mode, source='operator')

    def set_from_http(self, data) -> dict:
        """HTTP edge: never raise at the operator, answer with the reason."""
        try:
            request = MazdaModeRequest.from_http(data)
        except (ValidationError, ValueError) as exc:
            current = self.current().to_http()
            current['ok'] = False
            current['error'] = str(exc)
            return current
        return self.set(request).to_http()
