"""Subprocess boundary for bounded manual receipt reads."""
from __future__ import annotations

import argparse
import json

from finance.receipt_prefill_prompts import prompt_for
from finance.receipt_prefill_providers import read_with_provider
from finance.receipt_read_contracts import ReceiptReadIntent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument(
        '--intent', required=True,
        choices=[
            ReceiptReadIntent.CIRCLED_ONLY.value,
            ReceiptReadIntent.TOTAL_ONLY.value,
        ],
    )
    args = parser.parse_args()
    intent = ReceiptReadIntent(args.intent)
    try:
        reading, actual_model = read_with_provider(
            args.image, args.model, prompt_for(intent))
        if intent is ReceiptReadIntent.CIRCLED_ONLY \
                and not reading.has_marked_items:
            raise ValueError('No circled or otherwise locally marked items were found')
        payload = reading.to_prefill()
        missing = [
            key for key in ('merchant_name', 'transaction_date', 'total_amount')
            if payload.get(key) is None
        ]
        if missing:
            raise ValueError(
                'The model could not read required field(s): '
                + ', '.join(missing))
        print(json.dumps({
            'ok': True,
            'actual_model': actual_model,
            **payload,
        }))
        return 0
    except Exception as exc:
        print(json.dumps({
            'ok': False,
            'error': f'{type(exc).__name__}: {exc}',
        }))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
