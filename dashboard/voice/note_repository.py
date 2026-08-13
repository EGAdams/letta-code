"""Filesystem NoteRepository.

Toyota chooses a *descriptive* name; this class is what makes that name safe and
unique. Keeping the two apart matters: a model-supplied string is untrusted
input, and path safety is not something to re-derive inside a prompt.
"""
import datetime
import os
import re

from . import config
from .note_models import SavedNote
from .note_ports import NoteRepository

_UNSAFE = re.compile(r"[^a-z0-9]+")
_MAX_STEM = 60


def slugify(name: str) -> str:
    """Reduce an arbitrary name to a safe filename stem, or "" if nothing is left."""
    stem = _UNSAFE.sub("-", str(name or "").strip().lower()).strip("-")
    return stem[:_MAX_STEM].strip("-")


class FilesystemNoteRepository(NoteRepository):
    def __init__(self, directory=None, clock=None):
        self.directory = directory or config.NOTES_DIR
        # Injected so the date prefix is deterministic under test.
        self._now = clock or datetime.datetime.now

    def _stem(self, filename: str) -> str:
        return slugify(filename) or "note"

    def _unique_path(self, stem: str) -> "tuple[str, str]":
        prefix = self._now().strftime("%Y-%m-%d")
        candidate = f"{prefix}_{stem}.md"
        path = os.path.join(self.directory, candidate)
        counter = 2
        while os.path.exists(path):
            candidate = f"{prefix}_{stem}-{counter}.md"
            path = os.path.join(self.directory, candidate)
            counter += 1
        return candidate, path

    def save(self, note: str, filename: str = "") -> SavedNote:
        os.makedirs(self.directory, exist_ok=True)
        name, path = self._unique_path(self._stem(filename))
        text = note if note.endswith("\n") else f"{note}\n"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return SavedNote(filename=name, path=path)


def build_note_repository(directory=None) -> NoteRepository:
    return FilesystemNoteRepository(directory)
