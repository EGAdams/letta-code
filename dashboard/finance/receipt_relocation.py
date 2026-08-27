"""Rename a stored expense's receipt file when its filing identity changes.

A date or amount edit means the row's id_light no longer names the file that
is actually sitting on disk (`<vendor>_MM_DD_YY_<dollars>_<cents>.<ext>`, the
same shape finance/archive_path.py builds and finance/receipt_filename.py
parses). Left alone, that is a silent desync: "View Receipt" and the
by-(date,amount) receipt index both key off the filename, not the database
row. This module is the one place that turns "the row changed" into "the file
on disk changed to match" -- an ABC port so MySqlExpenseRecordRepository never
touches os.replace() directly, and a test can substitute a fake filesystem.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict


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
        if os.path.exists(new_path):
            return ReceiptRelocationResult(
                warning=f'Filing key changed to "{new_id_light}", but a file '
                        f'already exists at {new_path}; the old receipt file '
                        'was left in place.')
        try:
            self._replace(old_path, new_path)
        except OSError as exc:
            return ReceiptRelocationResult(
                warning=f'Filing key changed to "{new_id_light}", but '
                        f'renaming its receipt file failed: {exc}')
        return ReceiptRelocationResult(
            relocated=True, new_receipt_url=os.path.basename(new_path))
