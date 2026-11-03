"""Content-addressed, immutable copies of scan output.

`put_file` reads the scanner's output ONCE into memory, so the hash and the
stored bytes are the same bytes even if the scanner overwrites the file a
moment later. Reads are by sha only -- never by a caller-supplied path -- and
re-verify the hash, so a swapped or corrupted file is an error, not a document.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Optional

SHA_RE = re.compile(r'^[0-9a-f]{64}$')
DERIVED_NAME_RE = re.compile(r'^[a-z0-9_.-]{1,64}$')
MAX_ARTIFACT_BYTES = 60 * 1024 * 1024

_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b'\xff\xd8\xff', 'image/jpeg', 'jpg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png', 'png'),
    (b'%PDF-', 'application/pdf', 'pdf'),
)
_EXT = {mime: ext for _, mime, ext in _MAGIC}


class ArtifactError(Exception):
    """Capture or read refused; `code` is the API's error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sniff_mime(data: bytes) -> Optional[str]:
    return next((mime for magic, mime, _ in _MAGIC if data.startswith(magic)), None)


class FileArtifactStore:
    def __init__(self, root: Path, max_bytes: int = MAX_ARTIFACT_BYTES):
        self._root = Path(root)
        self._max = max_bytes
        for sub in ('blobs', 'derived', 'tmp'):
            (self._root / sub).mkdir(parents=True, exist_ok=True)
        os.chmod(self._root, 0o700)
        self._real_root = os.path.realpath(self._root)

    def put_file(self, source_path: str, not_before_ns: int) -> tuple[str, str, int]:
        """Copy the scanner's output in; returns (sha256, mime, size)."""
        try:
            fd = os.open(source_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        except OSError as exc:
            raise ArtifactError('capture_failed', f'scan output unreadable: {exc.strerror}') from exc
        with os.fdopen(fd, 'rb') as src:
            info = os.fstat(src.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ArtifactError('capture_failed', 'scan output is not a regular file')
            if info.st_mtime_ns < not_before_ns:
                raise ArtifactError('stale_output', 'scan output predates this scan; refusing an old image')
            data = src.read(self._max + 1)
        if not data:
            raise ArtifactError('empty_output', 'scan output is empty')
        if len(data) > self._max:
            raise ArtifactError('capture_failed', 'scan output exceeds the size limit')
        mime = sniff_mime(data)
        if mime is None:
            raise ArtifactError('unsupported_type', 'scan output is not a JPEG, PNG or PDF')
        sha = hashlib.sha256(data).hexdigest()
        target = self._blob_path(sha, mime)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(target, data)
        return sha, mime, len(data)

    def read(self, sha256: str) -> bytes:
        if not SHA_RE.match(sha256 or ''):
            raise ArtifactError('invalid_artifact', 'invalid artifact id')
        for mime in _EXT:
            path = self._blob_path(sha256, mime)
            if os.path.lexists(path):
                data = self._safe_read(path)
                if hashlib.sha256(data).hexdigest() != sha256:
                    raise ArtifactError('artifact_corrupt', 'stored artifact failed its integrity check')
                return data
        raise ArtifactError('artifact_missing', 'artifact not found')

    def get_derived(self, sha256: str, name: str) -> Optional[bytes]:
        path = self._derived_path(sha256, name)
        return self._safe_read(path) if os.path.lexists(path) else None

    def put_derived(self, sha256: str, name: str, data: bytes) -> None:
        path = self._derived_path(sha256, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, data)

    # -- internals -----------------------------------------------------------------
    def _blob_path(self, sha: str, mime: str) -> Path:
        return self._root / 'blobs' / sha[:2] / f'{sha}.{_EXT[mime]}'

    def _derived_path(self, sha: str, name: str) -> Path:
        if not SHA_RE.match(sha or '') or not DERIVED_NAME_RE.match(name or '') or '..' in name:
            raise ArtifactError('invalid_artifact', 'invalid derived artifact name')
        return self._root / 'derived' / sha[:2] / sha / name

    def _safe_read(self, path: Path) -> bytes:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ArtifactError('artifact_corrupt', 'artifact is not a regular file')
        real = os.path.realpath(path)
        if os.path.commonpath([real, self._real_root]) != self._real_root:
            raise ArtifactError('artifact_corrupt', 'artifact escapes the store')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as src:
            return src.read(self._max + 1)

    def _atomic_write(self, target: Path, data: bytes) -> None:
        tmp = self._root / 'tmp' / f'{target.name}.{os.getpid()}.{os.urandom(4).hex()}'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                tmp.unlink()
