"""The contract every health check answers with.

Ninety-two return statements in server.py build the same little dict by hand.
Four shapes exist between them, and the difference between the shapes is not
cosmetic -- it decides what colour a tab goes and whether the Restart button
is offered:

    {'ok': ...,  'text': ...}                  the ordinary answer
    {'ok': ...,  'text': ..., 'concern': True} up, but needs attention: yellow
    {'ok': False,'text': ..., 'hard': True}    down, and a restart will not fix it
    {'ok': ...,  'text': ..., 'name': ...}     a sub-check inside a rollup

`hard` is the one worth being careful with. `compute_server_status` offers the
Restart button for any restartable service that is down -- unless the check
said `hard`, meaning the cause is outside this box (an expired OAuth token, a
credential a click cannot regenerate). Spelling it `hard_failure`, or dropping
it while refactoring, silently puts a button in front of the operator that
cannot possibly work, and they will press it.

`ok` and `text` are both required, deliberately. A check that returns no text
renders as a green or red dot with nothing beside it, which tells the reader
that something is fine or broken but not what.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProbeResult(BaseModel):
    """One health check's answer.

    Dumped to a plain dict before it leaves, so the JSON is byte-for-byte what
    the hand-built dicts produced and the frontend is untouched. The optional
    flags are omitted rather than defaulted into the payload, because
    `compute_server_status` tests them with `.get()` and a `False` would read
    the same -- but the eight sub-check shapes would gain two keys they never
    had, and the rollups iterate them.
    """

    model_config = ConfigDict(extra='forbid')

    ok: bool
    #: Always say something. A dot with no words is not a health report.
    text: str = Field(min_length=1)
    #: Reachable and working, but degraded: yellow rather than green.
    concern: bool = False
    #: Down for a reason a Restart click cannot address. Suppresses the button.
    hard: bool = False
    #: Set only by sub-checks inside a rollup, which are listed by name.
    name: Optional[str] = None

    def to_payload(self) -> dict:
        out = {'ok': self.ok, 'text': self.text}
        if self.name is not None:
            out['name'] = self.name
        if self.concern:
            out['concern'] = True
        if self.hard:
            out['hard'] = True
        return out


def probe(ok: bool, text: str, **flags) -> dict:
    """Shorthand for the payload of one check: `probe(True, 'SDK OK')`.

    Exists so a call site reads as one line, the way the dict literal it
    replaces did. Validation still happens -- a misspelled flag raises here
    rather than being carried silently into the payload.
    """
    return ProbeResult(ok=ok, text=text, **flags).to_payload()
