"""What a receipt read actually told us, as a value instead of a bare pair.

`preview_receipt_parse` answers `(ok, payload)`. That is enough to fill a form
and nothing else, so every caller that wanted to know *why* a read failed had
to re-derive it from loose dictionary keys -- and the one caller that needed it
most, ForensicReceiptReadStrategy, did not bother and simply reported failure.

The defect that produced this module: the forensic reader decides shape once,
from `mazda_intake.py`'s classifier, and when that classifier says 'unknown' it
guesses receipt. The receipt reader then produces far better evidence -- Gemini
answering "this page has no one date and no one merchant" -- and that evidence
was thrown away, leaving the operator an empty form and, worse, the quota error
from a *later* model in the ladder. Deciding shape before reading and then
ignoring what the read said is exactly the weakness the five-reading-buttons
redesign was meant to remove; it survived here in a smaller form.

So shape becomes revisable rather than final, on one fact: the model ANSWERED
and still could not name a date or a merchant (`engine_failure`, from
receipt_engine.py's ReceiptShapeMismatch). That is worth *re-reading* the page
as a statement -- not concluding it is one.

The conclusion belongs to the statement reader, which is the only thing that
can settle it by finding transactions or not. An earlier version of this module
required `possible_statement` -- the OCR keyword heuristic -- to agree before
retrying, and on the live window scan that heuristic said False about a page
that is unmistakably a statement, blocking the retry entirely. It is the same
heuristic that scored the DTE gas bill 0. Asking a weak guess for permission to
consult the authority is how the original defect worked; `possible_statement`
is kept as corroborating detail and given no vote.

The cost of retrying and being wrong is one reader call and a slightly less
specific message on a genuinely unreadable receipt. The cost of not retrying is
an operator staring at an empty form holding a page full of transactions. The
asymmetry decides it.
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
    #: The OCR keyword heuristic's opinion. Reported, never obeyed -- see
    #: warrants_statement_retry.
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
    def warrants_statement_retry(self) -> bool:
        """Worth reading again as a statement -- not proof that it is one.

        Deliberately does NOT consult `possible_statement`. That heuristic
        answered False for the live window scan, a page that is plainly a
        statement, and scored the DTE gas bill 0 before it. Letting it veto the
        retry would put a weak guess in charge of whether the authority ever
        gets asked.

        A successful read is never second-guessed: if the model produced a
        merchant, a date and a total, the page is a receipt.
        """
        if self.ok:
            return False
        failure = self.engine_failure
        return bool(failure and failure.answered)

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
