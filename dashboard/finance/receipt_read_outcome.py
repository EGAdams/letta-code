"""What a receipt read actually told us, as a value instead of a bare pair.

`preview_receipt_parse` answers `(ok, payload)`. That is enough to fill a form
and nothing else, so every caller that wanted to know *why* a read failed had
to re-derive it from loose dictionary keys -- and the one caller that needed it
most, MazdaFillService, did not bother and simply reported failure.

The defect that produced this module: Mazda Fill decides a page's shape once,
from `mazda_intake.py`'s classifier, and when that classifier says 'unknown' it
guesses receipt. The receipt reader then produces far better evidence -- Gemini
answering "this page has no one date and no one merchant" -- and that evidence
was thrown away, leaving the operator an empty form and, worse, the quota error
from a *later* model in the ladder. Deciding shape before reading and then
ignoring what the read said is exactly the weakness the five-reading-buttons
redesign was meant to remove; it survived here in a smaller form.

So shape becomes revisable rather than final. The rule needs two facts that
live on opposite sides of a process boundary, which is why it is a type here
and not an `if` in the service:

* the model ANSWERED and still could not name a date or a merchant
  (`engine_failure`, from receipt_engine.py's ReceiptShapeMismatch), and
* the page's own text reads as a transaction table (`possible_statement`).

Either alone is a bad reason to re-read a page as a statement. A faded receipt
with an unreadable date satisfies the first; a receipt printed with several
line items can satisfy the second. Together they are the signature of a page
carrying many transactions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from finance.statement_models import StrictBoundaryModel

#: `kind` values receipt_engine.py's ReceiptShapeMismatch.as_dict() can send.
#: A model answered, and could not give the page a receipt's identity.
NO_RECEIPT_IDENTITY = 'no_receipt_identity'


class EngineFailure(StrictBoundaryModel):
    """Why the chosen model did not fill the form, in its own words.

    Crosses the process boundary from parse_and_categorize.py, which stamps it
    on the local-fallback report's `meta`. Absent for every failure that is not an *answer* --
    a 429, a 503, a missing key -- because those mean nobody read the document
    and there is nothing for a caller to reason about beyond "try again".
    """

    kind: str = ''
    model: str = ''
    missing: tuple[str, ...] = ()
    message: str = ''

    @classmethod
    def from_payload(cls, payload: Any) -> Optional['EngineFailure']:
        """Read one out of a reader's payload, or None if it isn't there.

        Tolerant on the way in because the producer is a separate repository on
        a separate release cycle: an older parse_and_categorize.py simply omits
        the key, and must keep working rather than raising here.
        """
        if not isinstance(payload, Mapping):
            return None
        raw = payload.get('engine_failure')
        if not isinstance(raw, Mapping):
            return None
        missing = raw.get('missing')
        return cls(
            kind=str(raw.get('kind') or ''),
            model=str(raw.get('model') or ''),
            missing=tuple(
                str(f) for f in missing if isinstance(f, str)
            ) if isinstance(missing, (list, tuple)) else (),
            message=str(raw.get('message') or ''),
        )

    @property
    def answered(self) -> bool:
        """The model looked at the document and reported back.

        The whole point of the distinction: an engine that never answered is
        worth asking again with a different model, and one that answered is
        not -- it will say the same thing and spend another request saying it.
        """
        return self.kind == NO_RECEIPT_IDENTITY


class ReceiptReadOutcome(StrictBoundaryModel):
    """One receipt read, as something a caller can ask questions of."""

    ok: bool
    error: str = ''
    possible_statement: bool = False
    engine_failure: Optional[EngineFailure] = None

    @classmethod
    def from_reader(cls, ok: bool, payload: Any) -> 'ReceiptReadOutcome':
        data = payload if isinstance(payload, Mapping) else {}
        return cls(
            ok=bool(ok),
            error=str(data.get('error') or ''),
            possible_statement=bool(data.get('possible_statement')),
            engine_failure=EngineFailure.from_payload(data),
        )

    @property
    def suggests_statement(self) -> bool:
        """Both signals, never one.

        A successful read is never second-guessed here: if the model produced a
        merchant, a date and a total, the page is a receipt and the operator
        can see for themselves whether it isn't.
        """
        if self.ok:
            return False
        failure = self.engine_failure
        return bool(failure and failure.answered and self.possible_statement)

    @property
    def best_error(self) -> str:
        """The engine's own sentence, when it has one.

        A model that answered said something specific and useful ("found no
        transaction date and no merchant name"). The generic wrapper text is
        what a caller falls back to when nobody looked at the document at all.
        """
        failure = self.engine_failure
        if failure and failure.message:
            return failure.message
        return self.error
