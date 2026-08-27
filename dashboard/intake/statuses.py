"""The intake status vocabulary, as a Literal rather than a set of strings.

Round 13 of the server.py refactor (Registry). Round 11 flagged
`_TERMINAL_INTAKE_STATUSES` as the natural first `Literal` of the intake block;
this is it.

What "terminal" decides
-----------------------
Two things, and both of them fail quietly:

* `merge_recent_intake_status()` **drops any update whose status is not in this
  set** and returns False. A status the Trainer sends that this set does not
  know is not an error anywhere — the record simply never lands, and the
  document sits on `processing` forever. That is round 11's defect, the sixth of
  the round-6 postscript's family: a scanned receipt that looks, on the page,
  exactly like one still being worked on.
* The Recent Report page stops its 30s auto-refresh on a terminal status. A
  terminal status missing from the set spins forever; a non-terminal one
  wrongly listed stops the page updating while work is still happening.

So this is a vocabulary, not a list of magic strings, and it is spelled once.
"""

from __future__ import annotations

from typing import Literal, get_args

#: A status that ends this run of an intake. Nothing more will happen for it.
TerminalIntakeStatus = Literal[
    'pass',
    'corrected',
    'fail',
    'stalled',
    'complete',
    # Nothing more happens on THIS run once a human needs to pick a vendor —
    # stop the Recent Report page's 30s auto-refresh, same as any other finished
    # run (see list_pending_vendor_review() / set_receipt_vendor()).
    'awaiting_vendor_review',
    # MAZDA_DECISION_MODE=human_only: Mazda's turn never started at all, so
    # there is no STEP 8 report-back to wait for — stop auto-refresh here too.
    'needs_human_review',
]

#: The same vocabulary as a set, for the membership tests that read it.
TERMINAL_INTAKE_STATUSES: frozenset[str] = frozenset(get_args(TerminalIntakeStatus))


def is_terminal(status: str | None) -> bool:
    """True when `status` ends the run.

    Callers normalise before asking (`str(...).strip().lower()`), and so does
    this — `min_length=1` is not "not blank" when the consumer strips, and
    membership of a set is not a match when the caller did not.
    """
    return str(status or '').strip().lower() in TERMINAL_INTAKE_STATUSES
