"""Rename a stored expense's receipt file when its filing identity changes.

A date or amount edit means the row's id_light no longer names the file that
is actually sitting on disk (`<vendor>_MM_DD_YY_<dollars>_<cents>.<ext>`, the
same shape finance/archive_path.py builds and finance/receipt_filename.py
parses). Left alone, that is a silent desync: "View Receipt" and the
by-(date,amount) receipt index both key off the filename, not the database
row. This module is the one place that turns "the row changed" into "the file
on disk changed to match" -- an ABC port so MySqlExpenseRecordRepository never
touches os.replace() directly, and a test can substitute a fake filesystem.

`replace_file_if_clear` is the lower-level primitive underneath the port: the
exists-check-then-replace policy that finance/recent_report_image.py's
RecentReportImageSynchronizer also needs for its own (pointer-cache-keyed)
rename. Both used to carry their own copy of that policy; sharing one means a
fix to how collisions or a vanished source are handled applies to both paths
at once, and is also why the two calls compose safely when a single edit
triggers them back to back.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict


class FileReplaceOutcome(BaseModel):
    """What happened when replace_file_if_clear tried to rename one file.

    `reason` is only meaningful when `moved` is False: 'missing_source' (the
    file to rename is already gone -- possibly because something else already
    made this exact move), 'target_exists' (a real collision, the old file is
    still there too), or 'error' (the OS refused the rename; `detail` carries
    the exception text).
    """
    model_config = ConfigDict(frozen=True)

    moved: bool = False
    reason: str = ''
    detail: str = ''


def replace_file_if_clear(old_path: str, new_path: str, *,
                          replace: Callable[[str, str], None] = os.replace,
                          ) -> FileReplaceOutcome:
    """Rename old_path -> new_path without os.replace()'s two sharp edges:
    silently clobbering an existing target, and raising FileNotFoundError up
    through a caller that has no source file to explain.

    The single primitive both receipt-renaming paths in this codebase share
    (FilesystemReceiptFileRelocator, and RecentReportImageSynchronizer's own
    pointer-cache bookkeeping) -- before this, each had its own copy of the
    same exists-check-then-replace logic, which was exactly how the two could
    ever race each other on the same file in the first place.
    """
    if old_path == new_path:
        return FileReplaceOutcome(moved=True)
    if not os.path.exists(old_path):
        # Nothing to move from. If the target is already sitting there, some
        # other caller made this exact move first -- not a fault, just a
        # winner already decided.
        return FileReplaceOutcome(
            moved=os.path.exists(new_path), reason='missing_source')
    if os.path.exists(new_path):
        return FileReplaceOutcome(reason='target_exists')
    try:
        replace(old_path, new_path)
    except OSError as exc:
        return FileReplaceOutcome(reason='error', detail=str(exc))
    return FileReplaceOutcome(moved=True)


class ReceiptRelocationResult(BaseModel):
    """What happened when a repository asked to rename a receipt file.

    `relocated=False` with an empty `warning` means "there was nothing to do"
    (no receipt on record, or the filing key did not actually change) --
    distinct from `relocated=False` with a `warning`, which means a rename was
    owed and failed, and the operator needs to know their row and its receipt
    file now disagree.
    """
    model_config = ConfigDict(frozen=True)

    relocated: bool = False
    #: New basename to persist as receipt_url. Empty when relocated is False.
    new_receipt_url: str = ''
    warning: str = ''


class IReceiptFileRelocator(ABC):
    """Port: move one receipt file to the name its corrected filing key implies."""

    @abstractmethod
    def relocate(self, *, receipt_url: str, old_id_light: str,
                 new_id_light: str) -> ReceiptRelocationResult:
        """Rename the file `receipt_url` resolves to so its name matches
        `new_id_light`. A no-op (not a failure) when the two id_lights are
        the same or there is nothing to resolve."""


class NullReceiptFileRelocator(IReceiptFileRelocator):
    """Default when no real filesystem is wired in (e.g. bare unit tests).

    Attempting nothing is the fail-closed choice here: a repository that
    silently claimed success without ever touching a disk would be worse than
    one that visibly does nothing until the composition root wires the real
    thing in.
    """

    def relocate(self, *, receipt_url, old_id_light, new_id_light):
        return ReceiptRelocationResult()


class FilesystemReceiptFileRelocator(IReceiptFileRelocator):
    """The real implementation: resolves receipt_url to a file on disk and
    os.replace()s it to the name the new id_light implies.

    `resolve_path` is injected rather than imported because the real resolver
    (server.py's _resolve_receipt_url_path) walks a receipt index built from
    every mounted receipt tree -- composition-root knowledge this module has
    no business owning.
    """

    def __init__(self, *, resolve_path: Callable[[str], Optional[str]],
                 replace: Callable[[str, str], None] = os.replace):
        self._resolve_path = resolve_path
        self._replace = replace

    def relocate(self, *, receipt_url, old_id_light,
                new_id_light) -> ReceiptRelocationResult:
        if not receipt_url or not old_id_light or old_id_light == new_id_light:
            return ReceiptRelocationResult()
        old_path = self._resolve_path(receipt_url)
        if not old_path:
            return ReceiptRelocationResult(
                warning=f'Filing key changed to "{new_id_light}", but its '
                        f'receipt file ({receipt_url}) could not be found on '
                        'disk to rename.')
        extension = os.path.splitext(old_path)[1] or '.jpg'
        new_path = os.path.join(os.path.dirname(old_path), new_id_light + extension)
        outcome = replace_file_if_clear(old_path, new_path, replace=self._replace)
        if not outcome.moved:
            if outcome.reason == 'target_exists':
                return ReceiptRelocationResult(
                    warning=f'Filing key changed to "{new_id_light}", but a '
                            f'file already exists at {new_path}; the old '
                            'receipt file was left in place.')
            if outcome.reason == 'missing_source':
                return ReceiptRelocationResult(
                    warning=f'Filing key changed to "{new_id_light}", but its '
                            f'receipt file ({receipt_url}) vanished from disk '
                            'while the rename was in progress.')
            return ReceiptRelocationResult(
                warning=f'Filing key changed to "{new_id_light}", but '
                        f'renaming its receipt file failed: {outcome.detail}')
        return ReceiptRelocationResult(
            relocated=True, new_receipt_url=os.path.basename(new_path))
