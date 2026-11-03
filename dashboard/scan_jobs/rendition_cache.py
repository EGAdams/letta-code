"""Rendered pages cached as plain .jpg files, not base64 inside JSON.

A rendition used to be cached as `RenderedPage.model_dump_json()`, which
base64-encodes the JPEG: a third bigger than the picture itself, and a "full"
page of a scanner JPEG ended up larger than the scan it came from. Now each
rendition is two derived files beside the original's hash:

    page{n}_{rendition}.jpg        the JPEG bytes, as is
    page{n}_{rendition}.meta.json  page, rendition, width, height, sha256

and a rendition that *is* the original (a full page of a JPEG that needed no
turning or shrinking) stores only the meta, flagged `original`, so the picture
is kept once. The old `page{n}_{rendition}.json` entries are never read again;
they hold pages rendered before rotation and can be deleted at leisure.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from contracts import StrictModel
from scan_jobs.models import RenderedPage
from scan_jobs.ports import IScanArtifactStore


class _RenditionMeta(StrictModel):
    page: int
    rendition: str
    width: int
    height: int
    sha256: str
    original: bool = False


class RenditionCache:
    def __init__(self, store: IScanArtifactStore):
        self._store = store

    def get(self, sha: str, page: int, rendition: str, original: bytes) -> Optional[RenderedPage]:
        stem = f'page{page}_{rendition}'
        raw = self._store.get_derived(sha, f'{stem}.meta.json')
        if not raw:
            return None
        meta = _RenditionMeta.model_validate_json(raw)
        jpeg = original if meta.original else self._store.get_derived(sha, f'{stem}.jpg')
        if not jpeg or hashlib.sha256(jpeg).hexdigest() != meta.sha256:
            return None                                   # half-written or stale: render again
        return RenderedPage(page=meta.page, rendition=meta.rendition, width=meta.width,
                            height=meta.height, sha256=meta.sha256, jpeg=jpeg)

    def put(self, sha: str, rendered: RenderedPage, original: bytes) -> None:
        stem = f'page{rendered.page}_{rendered.rendition}'
        is_original = rendered.jpeg == original
        if not is_original:
            self._store.put_derived(sha, f'{stem}.jpg', rendered.jpeg)
        meta = _RenditionMeta(page=rendered.page, rendition=rendered.rendition, width=rendered.width,
                              height=rendered.height, sha256=rendered.sha256, original=is_original)
        self._store.put_derived(sha, f'{stem}.meta.json', meta.model_dump_json().encode())   # last: commits
