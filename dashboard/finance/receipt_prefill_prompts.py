"""Prompt strategies for the two bounded receipt-reading jobs."""
from __future__ import annotations

from finance.receipt_read_contracts import ReceiptReadIntent


_JSON_RULE = """
Return only this JSON object, with no prose or markdown:
{"merchant_name":"string or null","transaction_date":"YYYY-MM-DD or null",
 "total_amount":12.34,"has_marked_items":false,
 "selection_evidence":"string or null"}
Do not return line items, addresses, phone numbers, raw OCR text, payment
details, category guesses, or any keys not shown above.
"""


def total_only_prompt() -> str:
    return """Read this receipt only far enough to fill three fields: the
merchant name, transaction date, and final printed amount actually charged.
Ignore item rows and handwriting unless needed to identify those three fields.
Set has_marked_items=false and selection_evidence=null.
""" + _JSON_RULE


def circled_only_prompt() -> str:
    return """Find a tight visible circle, box, checkmark, localized
highlight, or arrow that marks either (a) one or more purchased item rows, or
(b) the printed TOTAL amount itself. If item rows are marked, calculate
total_amount as the sum of those selected rows only and do not use the
printed receipt total. If instead the printed TOTAL amount is the thing
circled or boxed, that circled total IS the selection: set total_amount to
that printed total. A margin note, sweeping pen stroke, payment mark, or
handwritten arithmetic (for example a handwritten restatement of the total
written beside it) is not itself a selection mark, but it does not disqualify
a genuine circle/box drawn on an item row or on the printed total. If no
qualifying mark exists anywhere, set has_marked_items=false and
total_amount=null. Otherwise set has_marked_items=true and briefly identify
each local mark in selection_evidence. Also return the receipt merchant and
transaction date. Do not extract or return unselected item rows.
""" + _JSON_RULE


PROMPT_BUILDERS = {
    ReceiptReadIntent.CIRCLED_ONLY: circled_only_prompt,
    ReceiptReadIntent.TOTAL_ONLY: total_only_prompt,
}


def prompt_for(intent: ReceiptReadIntent) -> str:
    try:
        return PROMPT_BUILDERS[intent]()
    except KeyError as exc:
        raise ValueError(f'{intent.value} is not a focused read') from exc

