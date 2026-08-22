"""One button: let Mazda read the page, a human check it, a human save it.

The manual-entry form used to carry five reading buttons and a group box, and
the operator had to answer "is this one expense or several?" *before* pressing
anything -- a question only reading the document can answer. Local OCR was
wired in to guess it, and guessed wrong on any bill that spells its dates out
(the DTE gas bill, 2026-08-19, filed as one $28.07 expense because the
heuristic scored it 0).

This replaces all of that with the arrangement the pipeline already had:
`mazda_intake.py` classifies, then the matching reader extracts. Both are the
tools Mazda herself runs. The only thing the operator now chooses is which
cheap model does the reading -- and the result lands in the form for review
instead of being stored behind their back. Semi-automatic: Mazda reads,
a human decides.

Nothing here knows a script path, a subprocess, or an HTTP body. Every
collaborator appears once as an ABC (see IDocumentClassifier /
IReceiptReader), so server.py's composition root decides what satisfies it and
a test decides differently without touching a line of this file -- the same
arrangement finance/statement_ports.py already uses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Optional

from pydantic import field_validator

from finance.manual_entry import PREVIEW_ENGINES
from finance.receipt_read_outcome import ReceiptReadOutcome
from finance.statement_models import (
    STATEMENT_ENGINES,
    StatementBreakupRequest,
    StatementBreakupResponse,
    StrictBoundaryModel,
)

#: The models "Mazda Fill" may be asked to use.
#:
#: Deliberately the INTERSECTION of the two readers' own allow-lists, minus
#: the values that aren't a named cheap model: 'local' (tesseract -- the OCR
#: this whole module exists to stop relying on) and 'auto' (a fallback chain
#: whose later tiers are paid). One dropdown drives both readers, so a value
#: only one of them accepts would work on a receipt and 400 on a statement --
#: which is exactly the kind of split-brain failure the operator cannot
#: diagnose. assert_models_are_supported() pins this at import time.
MAZDA_FILL_MODELS: dict[str, str] = {
    'gemini-only': 'Gemini Flash',
    'haiku-only': 'Claude Haiku',
    # The ChatGPT/Codex subscription, read through the installed Codex CLI
    # (codex_cli_vision, EG's account then Mom's). "luna" is the model that
    # actually runs: the CLI default is gpt-5.6-luna.
    'codex-only': 'Codex (luna)',
}

DEFAULT_MAZDA_FILL_MODEL = 'gemini-only'

#: What the fill found, which is what the form does next: one row to check, or
#: a list of rows to walk with Prev/Next. Never a question put to the operator
#: -- it is an OUTPUT of reading the page, not an input to it.
SHAPE_ONE_EXPENSE = 'one-expense'
SHAPE_MANY_EXPENSES = 'many-expenses'


def assert_models_are_supported() -> None:
    """Fail loudly at import if a model here isn't accepted by BOTH readers.

    parse_and_categorize.py and parse_statement_scan.py keep independent
    --engine allow-lists across a process boundary. Adding a model to one
    without the other would otherwise surface as a cryptic argparse failure on
    whichever document kind happened to come next.
    """
    unsupported = sorted(
        set(MAZDA_FILL_MODELS) - (set(PREVIEW_ENGINES) & set(STATEMENT_ENGINES)))
    if unsupported:
        raise RuntimeError(
            'MAZDA_FILL_MODELS contains models one of the readers rejects: '
            f'{unsupported}. Add them to finance/manual_entry.PREVIEW_ENGINES '
            'and finance/statement_models.STATEMENT_ENGINES (and to the '
            'rol_finances scripts behind both) first.')


assert_models_are_supported()


class MazdaFillRequest(StrictBoundaryModel):
    """POST /api/mazda-fill's body."""

    image_path: str
    model: str = DEFAULT_MAZDA_FILL_MODEL
    #: Only ever sent on a RETRY, after a first pass reported it could not
    #: resolve the account from the page itself. Meaningless on a receipt and
    #: ignored there.
    bank_name: str = ''
    account_last4: str = ''

    @field_validator('image_path')
    @classmethod
    def _image_path_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('image_path is required')
        return value

    @field_validator('model')
    @classmethod
    def _known_model(cls, value: str) -> str:
        if value not in MAZDA_FILL_MODELS:
            raise ValueError(f'model must be one of {sorted(MAZDA_FILL_MODELS)}')
        return value

    @classmethod
    def from_http(cls, data: Mapping[str, Any] | None) -> 'MazdaFillRequest':
        data = data or {}
        return cls(
            image_path=str(data.get('image_path') or '').strip(),
            model=str(data.get('model') or DEFAULT_MAZDA_FILL_MODEL).strip(),
            bank_name=' '.join(str(data.get('bank_name') or '').split()),
            account_last4=str(data.get('account_last4') or '').strip(),
        )


class MazdaFillResponse(StrictBoundaryModel):
    """One response shape for both document kinds.

    `shape` tells the form which half to read. `receipt` carries
    preview_receipt_parse()'s prefill payload; `statement` carries
    StatementBreakupResponse.to_http(). Exactly one is populated -- the form
    has a single code path per shape rather than sniffing which keys arrived.
    """

    ok: bool
    shape: str
    model: str
    doc_kind: str = ''
    receipt: Optional[dict] = None
    statement: Optional[dict] = None
    #: Set only when the receipt read was overruled and the page was read again
    #: as a statement -- carries what the receipt reader said that changed the
    #: verdict. Blank on a first-time-right read. The form shows it so the
    #: operator can see the page was re-read and why, rather than silently
    #: getting a different kind of answer than the one they asked for.
    reread_after: str = ''
    error: Optional[str] = None

    def to_http(self) -> dict:
        return self.model_dump()


class IDocumentClassifier(ABC):
    """"Is this a receipt or a statement?" -- answered by reading it.

    The one question the operator used to have to answer by eye before
    pressing a button. Returns a doc_kind string (see server.py's
    STATEMENT_DOC_KINDS); '' means the classifier could not tell, which the
    service treats as a receipt because that is the recoverable guess -- a
    misread receipt shows the human three wrong fields, a misread statement
    silently discards every transaction but one.
    """

    @abstractmethod
    def classify(self, image_path: str) -> str:
        ...


class IReceiptReader(ABC):
    """The single-expense reader, as an interface.

    Returns preview_receipt_parse()'s own (ok, payload) pair unchanged -- the
    payload already carries the vendor-key/category resolution the form's
    dropdowns need, and re-shaping it here would be a second place for that
    contract to drift.
    """

    @abstractmethod
    def read(self, image_path: str, model: str) -> tuple[bool, Mapping[str, Any]]:
        ...


def _carries_transactions(response: 'MazdaFillResponse') -> bool:
    """Did the statement read actually come back with rows?

    The only question that settles whether a re-read was worth keeping. A
    needs_statement_metadata answer counts: every transaction was read and only
    the account identity is missing, which is a form the operator can finish.
    """
    payload = response.statement or {}
    rows = payload.get('transactions')
    return bool(isinstance(rows, (list, tuple)) and rows)


class MazdaFillService:
    """Classify, then hand the page to the reader built for its kind."""

    def __init__(self, classifier: IDocumentClassifier, receipts: IReceiptReader,
                 statements, statement_doc_kinds=('statement', 'bank_statement')):
        self._classifier = classifier
        self._receipts = receipts
        #: finance/statement_service.StatementBreakupService -- reused whole,
        #: not reimplemented. Its break_up() is the same call the retired
        #: "Read with Gemini"/"Read with Haiku" buttons made.
        self._statements = statements
        self._statement_doc_kinds = tuple(statement_doc_kinds)

    def fill(self, request: MazdaFillRequest) -> MazdaFillResponse:
        doc_kind = self._classify(request.image_path)
        if doc_kind in self._statement_doc_kinds:
            return self._fill_statement(request, doc_kind)
        return self._fill_receipt(request, doc_kind)

    def _classify(self, image_path: str) -> str:
        # A classifier that raises must not take the form down with it: the
        # operator can still type the expense in by hand, and the receipt
        # branch is the recoverable default.
        try:
            return str(self._classifier.classify(image_path) or '')
        except Exception:
            return ''

    def _fill_statement(self, request: MazdaFillRequest, doc_kind: str,
                        reread_after: str = '') -> MazdaFillResponse:
        breakup: StatementBreakupResponse = self._statements.break_up(
            StatementBreakupRequest(
                image_path=request.image_path,
                bank_name=request.bank_name,
                account_last4=request.account_last4,
                engine=request.model,
            ))
        payload = breakup.to_http()
        return MazdaFillResponse(
            # A needs_statement_metadata answer is NOT a failure: every
            # transaction was read and only the account identity is missing.
            # The form shows the rows while the operator types the bank in.
            ok=bool(payload.get('ok') or payload.get('needs_statement_metadata')),
            shape=SHAPE_MANY_EXPENSES,
            model=request.model,
            doc_kind=doc_kind,
            statement=payload,
            error=payload.get('error'),
            reread_after=reread_after,
        )

    def _fill_receipt(self, request: MazdaFillRequest,
                      doc_kind: str) -> MazdaFillResponse:
        ok, payload = self._receipts.read(request.image_path, request.model)
        prefill = dict(payload or {})
        outcome = ReceiptReadOutcome.from_reader(ok, prefill)
        # The read is allowed to overrule the classifier. `mazda_intake.py` gets
        # one look at the page and answers 'unknown' often enough that this
        # branch is where most scans land; the model that then actually READS
        # the page knows more than the guess that sent it here. Deciding shape
        # before reading, and then ignoring what the read said, is the weakness
        # that made a statement come back as an empty form and a quota error
        # from a model further down Gemini's ladder.
        #
        # Ask, then keep whichever answer has something in it. Nothing here
        # decides the page IS a statement -- the statement reader settles that
        # by finding transactions or not, which is more than any heuristic on
        # this side can honestly claim.
        if outcome.warrants_statement_retry:
            statement = self._fill_statement(
                request, doc_kind, reread_after=outcome.best_error)
            if _carries_transactions(statement):
                return statement
            # Neither reader found anything: the page really is an unreadable
            # receipt, so the operator should see what the RECEIPT reader said
            # about it, not a statement extractor's complaint about a page that
            # was never a statement.
        return MazdaFillResponse(
            ok=bool(ok),
            shape=SHAPE_ONE_EXPENSE,
            model=request.model,
            doc_kind=doc_kind,
            receipt={'ok': bool(ok), **prefill},
            error=outcome.best_error or None,
        )


class CallableDocumentClassifier(IDocumentClassifier):
    """Adapter: any doc_kind-returning callable satisfies the port."""

    def __init__(self, classify_fn):
        self._classify_fn = classify_fn

    def classify(self, image_path: str) -> str:
        return str(self._classify_fn(image_path) or '')


class CallableReceiptReader(IReceiptReader):
    """Adapter: preview_receipt_parse (or a fake) satisfies the port."""

    def __init__(self, read_fn):
        self._read_fn = read_fn

    def read(self, image_path: str, model: str) -> tuple[bool, Mapping[str, Any]]:
        return self._read_fn(image_path, model)
