"""Mazda's nine intake steps, with their positions pinned.

Round 13 of the server.py refactor (Registry). `_MAZDA_PROGRESS_LABELS` was a
tuple of nine strings in `server.py`, and `_mazda_progress_from_messages()`
builds a parallel `statuses` list of the same length and then indexes into it by
number:

    statuses[1] = 'skipped'   # classify, when doc_kind is already known
    statuses[2] = 'done'      # vendor/duplicate check, for statements
    statuses[7] = 'skipped'   # propose-improvement, when the judge passed

Those indices are only correct because the labels are in STEP order. Reorder the
tuple — or insert a step in the middle — and the progress panel marks the wrong
rows, which renders as a plausible-looking progress bar describing work that did
not happen. Nothing checked it.

`MazdaProgressStep` carries the step number the label already announces, and
`_check_the_steps_are_in_order()` asserts position == step number, so the
indices in `server.py` are guarded by the data they index into.
"""

from __future__ import annotations

import json
import re

from pydantic import field_validator

from contracts import StrictModel


class MazdaProgressStep(StrictModel):
    """One row of the intake progress panel.

    `label` is the rendered text and must keep its "STEP n — " prefix: the panel
    shows it verbatim, and an unlabelled stage renders as a blank progress line.
    """

    step: int
    label: str

    @field_validator('label')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                'a blank label renders as an empty progress row, which reads '
                'as a stage that does not exist')
        return value

    @field_validator('step')
    @classmethod
    def _is_a_step_number(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f'{value} is not a step number')
        return value


MAZDA_PROGRESS_STEPS: tuple[MazdaProgressStep, ...] = (
    MazdaProgressStep(step=0, label='STEP 0 — Load learned wrapper'),
    MazdaProgressStep(step=1, label='STEP 1 — Classify and parse document'),
    MazdaProgressStep(step=2, label='STEP 2 — Check vendor and duplicates'),
    MazdaProgressStep(step=3, label='STEP 3 — Categorize'),
    MazdaProgressStep(step=4, label='STEP 4 — Store'),
    MazdaProgressStep(step=5, label='STEP 5 — Record trace'),
    MazdaProgressStep(step=6, label='STEP 6 — Judge trace'),
    MazdaProgressStep(step=7, label='STEP 7 — Propose improvement if needed'),
    MazdaProgressStep(step=8, label='STEP 8 — Notify dashboard'),
)


def _check_the_steps_are_in_order() -> None:
    """Position must equal step number, and the label must say so.

    This is what makes `statuses[7] = 'skipped'` in server.py safe to write.
    """
    for index, step in enumerate(MAZDA_PROGRESS_STEPS):
        if step.step != index:
            raise ValueError(
                f'step {step.step} sits at position {index}; server.py indexes '
                'the parallel statuses list by position, so the progress panel '
                'would mark the wrong rows')
        if not step.label.startswith(f'STEP {index} '):
            raise ValueError(
                f'{step.label!r} is at position {index} but does not announce '
                'that step — the panel would show a number that disagrees with '
                'the row it is on')


_check_the_steps_are_in_order()


#: The legacy view: the nine labels, in order.
MAZDA_PROGRESS_LABELS: tuple[str, ...] = tuple(
    s.label for s in MAZDA_PROGRESS_STEPS)


def mazda_progress_from_messages(intake, messages):
    """Derive intake progress only from successful tool returns.

    Indexes a parallel ``statuses`` list BY POSITION (statuses[1], [2], [7]),
    which is only correct because MAZDA_PROGRESS_STEPS is in STEP order --
    guarded by ``_check_the_steps_are_in_order()`` above.
    """
    calls = {}
    returns = {}
    for message in messages or []:
        call = message.get('tool_call') or {}
        call_id = call.get('tool_call_id') or message.get('tool_call_id')
        if message.get('message_type') == 'tool_call_message' and call_id:
            calls[call_id] = call
        if message.get('message_type') == 'tool_return_message' and call_id:
            returns[call_id] = message

    statuses = ['pending'] * len(MAZDA_PROGRESS_LABELS)
    doc_kind = str((intake or {}).get('doc_kind') or 'unknown').lower()
    if doc_kind != 'unknown':
        statuses[1] = 'skipped'
    if doc_kind in ('statement', 'bank_statement'):
        statuses[2] = 'done'  # dashboard preflight validated metadata/rows

    def classify(call):
        name = str(call.get('name') or '')
        args = call.get('arguments') or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        command = str(
            args.get('command') or args.get('cmd') or args.get('input') or '')
        if name == 'load_wrapper_revision':
            return 0
        if name == 'executor_run':
            if ('classify_scan.py' in command
                    or 'parse_and_categorize.py' in command
                    and '--save' not in command
                    or 'parse_statement_scan.py' in command):
                return 1
            if 'categorizer_main.py' in command:
                return 3
            if ('parse_and_categorize.py' in command and '--save' in command
                    or 'store_statement_transactions.py' in command):
                return 4
            if '/api/expense-stored' in command:
                return 8
        if name in ('check_vendor_key', 'check_duplicates'):
            return 2
        if name == 'record_trace':
            return 5
        if name == 'judge_trace':
            return 6
        if name in ('propose_improvement', 'apply_proposal'):
            return 7
        return None

    judge_passed = False
    for call_id, call in calls.items():
        index = classify(call)
        if index is None:
            continue
        returned = returns.get(call_id)
        successful = bool(
            returned and str(returned.get('status') or 'success').lower()
            in ('success', 'ok', 'completed'))
        if successful:
            statuses[index] = 'done'
            if index == 6:
                content = returned.get('tool_return') or returned.get('content') or ''
                if isinstance(content, dict):
                    verdict = content.get('verdict')
                else:
                    match = re.search(r'"verdict"\s*:\s*"([^"]+)"', str(content))
                    verdict = match.group(1) if match else ''
                judge_passed = str(verdict).upper() == 'PASS'
        elif statuses[index] == 'pending':
            statuses[index] = 'active'
    if judge_passed:
        statuses[7] = 'skipped'

    steps = [
        {'label': label, 'status': status}
        for label, status in zip(MAZDA_PROGRESS_LABELS, statuses)
    ]
    completed = sum(status == 'done' for status in statuses)
    required = sum(status != 'skipped' for status in statuses)
    percent = round(completed * 100 / required) if required else 100
    return {
        'steps': steps,
        'completed': completed,
        'required': required,
        'percent': percent,
    }
