"""Strategy objects for deciding where a renamed receipt belongs."""
from __future__ import annotations

import calendar
import os
import re
from abc import ABC, abstractmethod
from datetime import date
from typing import Sequence


_ID_LIGHT_SUFFIX = re.compile(
    r'_(?P<month>\d{2})_(?P<day>\d{2})_(?P<year>\d{2})_'
    r'(?P<dollars>\d+)_(?P<cents>\d{2})$'
)


class IReceiptDestinationPolicy(ABC):
    """Strategy: map a corrected filing key to its complete filesystem path."""

    @abstractmethod
    def destination_for(self, source_path: str, new_id_light: str) -> str:
        """Return the full destination path without changing the filesystem."""


class SameDirectoryReceiptDestinationPolicy(IReceiptDestinationPolicy):
    """Compatibility strategy for non-archive callers and isolated tests."""

    def destination_for(self, source_path: str, new_id_light: str) -> str:
        extension = os.path.splitext(source_path)[1] or '.jpg'
        return os.path.join(os.path.dirname(source_path), new_id_light + extension)


class CanonicalReceiptDestinationPolicy(IReceiptDestinationPolicy):
    """File receipts under ``root/year/month/month_DD`` from their identity."""

    def __init__(self, receipt_roots: str | Sequence[str]):
        roots = ([receipt_roots] if isinstance(receipt_roots, str)
                 else list(receipt_roots))
        self._roots = tuple(os.path.abspath(os.path.expanduser(root))
                            for root in roots if str(root).strip())
        if not self._roots:
            raise ValueError('at least one receipt root is required')

    def _root_for(self, source_path: str) -> str:
        source = os.path.abspath(source_path)
        matches = [root for root in self._roots
                   if os.path.commonpath((source, root)) == root]
        if not matches:
            raise ValueError(f'receipt is outside configured roots: {source_path}')
        return max(matches, key=len)

    def destination_for(self, source_path: str, new_id_light: str) -> str:
        match = _ID_LIGHT_SUFFIX.search(new_id_light or '')
        if not match:
            raise ValueError(f'invalid receipt filing key: {new_id_light}')
        filed_date = date(
            2000 + int(match.group('year')),
            int(match.group('month')),
            int(match.group('day')),
        )
        month = calendar.month_name[filed_date.month].lower()
        extension = os.path.splitext(source_path)[1] or '.jpg'
        return os.path.join(
            self._root_for(source_path),
            str(filed_date.year),
            month,
            f'{month}_{filed_date.day:02d}',
            new_id_light + extension,
        )
