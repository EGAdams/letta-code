"""Keep a Recent Report intake's archived image name in sync with its rows."""
from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping, MutableMapping, Sequence

from finance.archive_path import build_id_light


class RecentReportImageSynchronizer:
    """Rename one intake artifact after an expense mutation.

    Persistence and row loading are injected because the JSON event store and
    MySQL repository belong to the dashboard composition root.  This object
    owns only the cross-record rule: one document name reflects its vendor,
    date, and the sum of the expense rows still associated with it.
    """

    def __init__(self, *, read_pointer: Callable[[], dict],
                 write_pointer: Callable[[dict], bool],
                 fetch_rows: Callable[[Sequence[int]], Sequence[Mapping]],
                 update_references: Callable[[Sequence[int], str], None] | None = None,
                 replace: Callable[[str, str], None] = os.replace):
        self._read_pointer = read_pointer
        self._write_pointer = write_pointer
        self._fetch_rows = fetch_rows
        self._update_references = update_references or (lambda _ids, _path: None)
        self._replace = replace

    @staticmethod
    def _intakes(data: Mapping) -> list[MutableMapping]:
        candidates = [data.get('intake')]
        scanners = data.get('scanner_intakes')
        if isinstance(scanners, Mapping):
            candidates.extend(scanners.values())
        return [item for item in candidates if isinstance(item, MutableMapping)]

    @staticmethod
    def _ids(intake: Mapping) -> list[int]:
        values = list(intake.get('expense_ids') or [])
        values += list(intake.get('duplicate_expense_ids') or [])
        result = []
        for value in values:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed not in result:
                result.append(parsed)
        return result

    @staticmethod
    def _amount(rows: Sequence[Mapping]) -> Decimal:
        total = Decimal('0')
        for row in rows:
            try:
                total += abs(Decimal(str(row.get('amount'))))
            except (InvalidOperation, TypeError, ValueError):
                continue
        return total.quantize(Decimal('0.01'))

    @staticmethod
    def _archived_identity(path: str) -> tuple[str, str] | None:
        """Vendor/date already stamped on a canonical receipt filename.

        A second expense describes an item bought at the store; it does not
        redefine the receipt's store. The existing archive name is therefore
        the authority for identity, while only its trailing amount is mutable.
        """
        stem = os.path.splitext(os.path.basename(path))[0]
        match = re.fullmatch(
            r'(?P<vendor>.+)_(?P<date>\d{2}_\d{2}_\d{2})_'
            r'(?P<dollars>\d+)_(?P<cents>\d{2})', stem)
        if not match:
            return None
        try:
            date = datetime.strptime(
                match.group('date'), '%m_%d_%y').date().isoformat()
        except ValueError:
            return None
        return match.group('vendor'), date

    def synchronize(self, expense_id: int, *, deleted: bool = False,
                    vendor_key: str = '', transaction_date: str = '',
                    fallback_vendor_key: str = '', fallback_date: str = '',
                    replace_identity: bool = False) -> dict:
        data = self._read_pointer()
        matched = [item for item in self._intakes(data)
                   if expense_id in self._ids(item)]
        if not matched:
            return {'renamed': False}

        representative = next(
            (item for item in matched if item.get('archive_paths')), matched[0])
        ids = self._ids(representative)
        if deleted:
            ids = [value for value in ids if value != expense_id]
        rows = list(self._fetch_rows(ids))
        first = rows[0] if rows else {}
        vendor = (vendor_key or first.get('vendor_key')
                  or fallback_vendor_key or 'receipt')
        date = (transaction_date or first.get('date')
                or first.get('expense_date') or fallback_date)
        if not date:
            return {'renamed': False, 'warning': 'No transaction date for image rename.'}

        paths = [str(path).strip()
                 for path in (representative.get('archive_paths') or [])
                 if str(path).strip()]
        if not paths:
            return {'renamed': False, 'warning': 'No archived image path to rename.'}
        old_path = paths[0]
        archived_identity = self._archived_identity(old_path)
        if archived_identity and not replace_identity:
            vendor, date = archived_identity
        extension = os.path.splitext(old_path)[1] or '.jpg'
        new_path = os.path.join(
            os.path.dirname(old_path),
            build_id_light(str(vendor), str(date), float(self._amount(rows))) + extension,
        )
        if new_path != old_path:
            if os.path.exists(new_path):
                if os.path.exists(old_path):
                    return {'renamed': False,
                            'warning': f'Image rename target already exists: {new_path}'}
                # old_path is already gone and new_path already exists: some
                # other mutation (e.g. the expense-edit repository's own
                # receipt relocation, see finance/receipt_relocation.py) beat
                # this call to the same rename. Nothing left to move -- just
                # catch this pointer's bookkeeping up to match.
            else:
                self._replace(old_path, new_path)
        self._update_references(ids, new_path)

        for intake in matched:
            intake['archive_paths'] = [
                new_path if str(path).strip() == old_path else path
                for path in (intake.get('archive_paths') or [])
            ]
            if os.path.basename(str(intake.get('document') or '')) == os.path.basename(old_path):
                intake['document'] = os.path.basename(new_path)
        if not self._write_pointer(data):
            # The rename already happened; report loudly instead of pretending
            # the pointer and disk still agree.
            return {'renamed': new_path != old_path, 'path': new_path,
                    'warning': 'Image renamed, but Recent Report metadata was not saved.'}
        return {'renamed': new_path != old_path, 'path': new_path}
