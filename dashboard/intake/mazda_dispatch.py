"""The one fork between Mazda's LLM turn and a human's inbox.

Everything expensive the intake pipeline can do happens *inside* Mazda's agent
turn -- the categorizer, the vision tier, parser selection. There is no way to
reach in and intercept a call three layers inside her reasoning, so the only
place a mode can stop the spend is before the turn starts. That place is
``dispatch_or_block``, and it is the reason this module exists as one file:
the decision, the two things it chooses between, and the record it writes when
it declines, are one story.

What it does not own
--------------------
The mode itself lives in ``intake.mazda_mode`` (the vocabulary, the operator's
switch, the env-var default). The Trainer's deadline watch lives in
``intake.trainer_escalation`` and is still assembled in server.py, so it
arrives here as a collaborator rather than an import -- see ``Collaborators``.

Why the outcome record is typed
-------------------------------
When this module declines to dispatch, the only trace is a status record
merged into ``recent_report.json``. Nothing checks whether that merge landed,
and the merge itself reads the record with ``.get()`` and defaults. Two of
those defaults do not fail loudly when a field is missing -- they switch a
guard off:

* a missing ``status_source`` becomes ``'trainer'``, and the late-callback
  recovery branch in ``_fold_event_into_intake`` only clears a provisional
  failure whose source is ``'transport'``. Blame the Trainer for a transport
  failure and the document can never be un-failed, even when its STEP 8
  callback proves Mazda got it.
* a missing ``conversation_id`` drops the primary correlation key, leaving a
  document-path-plus-timestamp fallback that can match nothing at all. The
  merge then returns False, nobody reads the return value, and the document
  stays on the non-terminal ``'processing'`` status forever -- the operator's
  page auto-refreshes on it for the rest of the day and the scan is, in
  practice, lost. That is precisely the outcome ``block_for_human_only``
  exists to prevent.

``IntakeOutcome`` requires both, and pins the (status, status_source) pairing,
because getting the pairing wrong is the same accident in the other direction:
a human-only block labelled ``'transport'`` would be silently flipped to
``'complete'`` by any stray callback and vanish from the manual queue.

``tests/test_mazda_dispatch.py`` records all of the above as the code that
used to run, so the day this model stops earning its keep is visible.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from contracts import StrictModel
from hosts import LETTA_BASE_URL
from intake.dispatch_evidence import DispatchEvidence
from intake.mazda_mode import SEMI_AUTOMATIC
from intake.scan_message import build_scan_message
from urllib.parse import quote

#: What the operator reads on /recent_report.html when the mode declined to
#: start Mazda. Also reused verbatim as the pipeline result's ``stage_error``.
HUMAN_ONLY_MODE_STAGE_MESSAGE = (
    'MAZDA_DECISION_MODE=human_only: Mazda and the Trainer were not started '
    'for this document. Process it manually — see /recent_report.html.')

TRANSPORT_FAILURE_DETAIL = (
    'Mazda could not be reached after the scan was staged. '
    'No transactions were stored; retry this scan when the '
    'Letta server is available.')

#: The only two ways this module ends a run without dispatching, and the
#: source label each one MUST carry. Written as a mapping rather than two
#: independent Literals so the pairing cannot drift: the source is what the
#: recovery branch keys off, and the status is what the operator sees.
OUTCOME_SOURCES: dict[str, str] = {
    'needs_human_review': 'human_only_mode',
    'fail': 'transport',
}


class IntakeOutcome(StrictModel):
    """A terminal status record for a document Mazda was never given.

    Dumps to exactly the dict the previous inline literals produced, so
    ``merge_recent_intake_status`` and the browser payload are byte-identical.
    """

    conversation_id: str = Field(min_length=1)
    document_path: str = Field(min_length=1)
    #: A unix timestamp, so gt=0 costs nothing legitimate and closes a third
    #: silent guard: ``IntakeCallback.from_mapping`` returns None for
    #: ``dispatched_at <= 0``, which makes ``observe_callback`` a no-op, which
    #: leaves the Trainer's deadline watch un-cancelled. It then fires and
    #: summons a Trainer for a document whose transport already failed -- a
    #: real, silent LLM spend on a run already known dead.
    dispatched_at: float = Field(gt=0)
    status: Literal['needs_human_review', 'fail']
    status_source: Literal['human_only_mode', 'transport']
    detail: str = Field(min_length=1)

    @field_validator('conversation_id', 'document_path', 'detail')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """``min_length`` alone is not enough here. Every consumer reads
        these through ``str(...).strip()``, so ``'   '`` is indistinguishable
        from absent by the time it matters -- and absent is what disables the
        correlation key. Same guard TrainerLaunchRequest uses, same reason."""
        if not value.strip():
            raise ValueError('value must not be blank')
        return value

    @model_validator(mode='after')
    def _source_must_match_status(self) -> 'IntakeOutcome':
        expected = OUTCOME_SOURCES[self.status]
        if self.status_source != expected:
            raise ValueError(
                f'status {self.status!r} must carry status_source '
                f'{expected!r}, not {self.status_source!r}')
        return self

    def as_update(self) -> dict:
        """The mapping ``merge_recent_intake_status`` reads."""
        return self.model_dump()


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call.

    ``watch_intake`` is the Trainer's, not ours: it is a thin wrapper over the
    escalation service server.py builds at import time. Rebuilding this bundle
    per call is what keeps a monkeypatched ``EXECUTION_MODE`` -- and a live
    flip of the operator's switch -- visible to the next document rather than
    frozen at whatever it was when the module was imported.
    """

    current_mode: Callable[[], str]
    watch_intake: Callable[..., Any]
    merge_status: Callable[[dict], bool]
    observe_callback: Callable[[dict], Any]
    letta_get: Callable[..., Any]


def block_for_human_only(deps: Collaborators, document_path, conversation_id,
                         dispatched_at) -> bool:
    """Semi-Automatic: the single point that replaces Mazda+Trainer construction.

    Records the same terminal-status shape a Trainer failure would, so the
    document surfaces on /recent_report.html as needing a human instead of
    silently vanishing — the operator still sees every scanned/PDF document,
    just routed to manual processing instead of Mazda's LLM turn. Never
    registers a Trainer watch either: with Mazda never dispatched, a deadline
    watch would eventually fire the ProblemOnlyTrainerEscalationService for a
    callback that can never arrive, spending exactly the tokens this mode
    exists to save.

    Returns whether the record actually landed. The old inline version
    discarded that answer; a False here means the operator will never be shown
    this document, which is worth a line in the log at minimum.
    """
    outcome = IntakeOutcome(
        conversation_id=conversation_id,
        document_path=document_path,
        dispatched_at=dispatched_at,
        status='needs_human_review',
        status_source='human_only_mode',
        detail=HUMAN_ONLY_MODE_STAGE_MESSAGE,
    )
    merged = bool(deps.merge_status(outcome.as_update()))
    if not merged:
        print(f'[intake] human_only block did not match any recorded intake '
              f'({document_path}; conversation={conversation_id}) — the '
              f'document will not appear on /recent_report.html')
    return merged


def dispatch_or_block(deps: Collaborators, document_path, label, facade,
                      conversation_id, dispatched_at,
                      mazda_thread_target, mazda_thread_args) -> bool:
    """The one fork point between Mazda's LLM turn and human-only blocking.

    process_scanned_document and process_pdf_document each used to carry this
    branch independently — duplicated mode-dependent logic. Returns
    mazda_dispatched. The Trainer is never dispatched synchronously from
    here in either mode: ProblemOnlyTrainerEscalationService (registered via
    ``watch_intake``) decides later, off a callback deadline, whether a run
    ever needed one — human_only skips registering that watch too, since Mazda
    never starting means no callback will ever arrive.
    """
    if deps.current_mode() == SEMI_AUTOMATIC:
        block_for_human_only(deps, document_path, conversation_id, dispatched_at)
        return False
    deps.watch_intake(document_path, label, facade, conversation_id, dispatched_at)
    threading.Thread(
        target=mazda_thread_target, args=mazda_thread_args, daemon=True).start()
    return True


def dispatch_was_accepted(deps: Collaborators, conversation_id) -> bool:
    """Confirm that a failed synchronous POST still reached its conversation.

    Letta keeps the non-streaming messages request open while the agent works,
    so an intake can outlive our HTTP timeout even though Letta accepted it.
    That is the case this exists for, and it still answers True there.

    It reads the conversation's MESSAGES rather than the conversation object's
    `in_context_message_ids`. The old check counted those ids and treated any
    of them as acknowledgement, on the premise that a new conversation is
    empty. It never is -- it carries its system prompt -- so the check answered
    "accepted" for a conversation nothing had ever been posted to. See
    intake/dispatch_evidence.py for what that cost on 2026-08-19.
    """
    if not conversation_id:
        return False
    messages = deps.letta_get(
        f'/v1/conversations/{quote(conversation_id, safe="")}/messages?limit=5',
        timeout=10)
    return DispatchEvidence.from_payload(messages).dispatch_landed


def notify_mazda_of_scan(deps: Collaborators, scan_image_path, scanner_name,
                         facade_result=None, conversation_id=None,
                         dispatched_at=None) -> bool:
    """Background: send the scanned document to Mazda for intake processing.

    scan_image_path must already be reachable from Mazda's executor tools
    (see _stage_scan_for_mazda) — this function does no staging itself.
    """
    if not conversation_id:
        print('[scan→mazda] Refusing shared/default conversation dispatch')
        return False
    try:
        msg = build_scan_message(
            scan_image_path, scanner_name, facade_result,
            conversation_id=conversation_id, dispatched_at=dispatched_at)
        payload = json.dumps({
            'messages': [{'role': 'user', 'content': msg}],
            'streaming': False,
        }).encode()
        req = urllib.request.Request(
            f'{LETTA_BASE_URL}/v1/conversations/{quote(conversation_id, safe="")}/messages',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(f'[scan→mazda] Mazda notified of scan ({scanner_name}): '
                  f'HTTP {resp.status}; conversation={conversation_id}')
        return True
    except Exception as exc:
        if dispatch_was_accepted(deps, conversation_id):
            print(f'[scan→mazda] Mazda accepted scan ({scanner_name}); '
                  f'the synchronous response ended late: {exc}; '
                  f'conversation={conversation_id}')
            return True
        print(f'[scan→mazda] Failed to notify Mazda: {exc}')
        return False


def notify_mazda_of_scan_and_record_failure(
        deps: Collaborators, scan_image_path, scanner_name, facade_result=None,
        conversation_id=None, dispatched_at=None) -> bool:
    """Dispatch a scan and make a transport failure visible in its report.

    The failure is *provisional*: ``status_source='transport'`` is the only
    label a late STEP 8 callback is allowed to clear, so it is the difference
    between a timed-out POST that Letta actually accepted being corrected to
    'complete' and it reading as a permanent failure forever.
    """
    notified = notify_mazda_of_scan(
        deps, scan_image_path, scanner_name, facade_result,
        conversation_id, dispatched_at)
    if notified:
        return True
    failure = IntakeOutcome(
        conversation_id=conversation_id,
        document_path=scan_image_path,
        dispatched_at=dispatched_at,
        status='fail',
        status_source='transport',
        detail=TRANSPORT_FAILURE_DETAIL,
    ).as_update()
    deps.observe_callback(failure)
    deps.merge_status(failure)
    return False
