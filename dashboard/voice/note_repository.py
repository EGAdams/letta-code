"""Filesystem NoteRepository.

Toyota chooses a *descriptive* name; this class is what makes that name safe and
unique. Keeping the two apart matters: a model-supplied string is untrusted
input, and path safety is not something to re-derive inside a prompt.

Deletion is soft: `delete` moves a note into `.trash/` inside the same
directory rather than unlinking it, so `restore` can bring it back. `.trash`
never appears in `list()` (it is a directory, and `list()` only reads the top
level), so it does not change what a caller already sees as "the notes."
"""
import datetime
import os
import re
import hashlib

from . import config
from .note_models import SavedNote
from .note_ports import NoteRepository

_UNSAFE = re.compile(r"[^a-z0-9]+")
_MAX_STEM = 60
TRASH_DIRNAME = ".trash"
_TRASH_NAME = re.compile(r"^\d{14}_(?:\d+_)?(?P<name>.+)$")


class NoteNameConflictError(FileExistsError):
    """The target filename for a rename/restore already names an existing note.

    A subclass of `FileExistsError` so an older caller that only catches that
    (as `write`'s stale-revision case already does) still catches this; a
    caller that needs to tell "the name is taken" apart from "the revision is
    stale" catches this one first.
    """


def slugify(name: str) -> str:
    """Reduce an arbitrary name to a safe filename stem, or "" if nothing is left."""
    stem = _UNSAFE.sub("-", str(name or "").strip().lower()).strip("-")
    return stem[:_MAX_STEM].strip("-")


def _original_name_from_trash(trashed_name: str) -> str:
    """Strip the `<timestamp>_[counter_]` prefix `delete` adds, for a default restore name."""
    match = _TRASH_NAME.match(trashed_name)
    return match.group("name") if match else trashed_name


class FilesystemNoteRepository(NoteRepository):
    def __init__(self, directory=None, clock=None):
        self.directory = directory or config.NOTES_DIR
        # Injected so the date prefix is deterministic under test.
        self._now = clock or datetime.datetime.now

    def _stem(self, filename: str) -> str:
        return slugify(filename) or "note"

    def _trash_dir(self) -> str:
        return os.path.join(self.directory, TRASH_DIRNAME)

    def _safe_path(self, filename: str, base_dir: "str | None" = None) -> str:
        """Resolve `filename` to an absolute path strictly inside `base_dir`
        (default `self.directory`).

        Rejects anything but a bare filename (no traversal via `/` or `..`),
        and rejects a symlink at that name outright -- a note is reachable
        only by its own name on disk, never by following a link elsewhere,
        including one whose resolved target happens to still land inside the
        directory.
        """
        base_dir = self.directory if base_dir is None else base_dir
        safe_name = os.path.basename(filename)
        candidate = os.path.join(base_dir, safe_name)
        if safe_name != filename or os.path.islink(candidate):
            raise ValueError("invalid note filename")
        path = os.path.realpath(candidate)
        root = os.path.realpath(base_dir)
        if not path.startswith(root + os.sep):
            raise ValueError("invalid note filename")
        return path

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

    def list(self):
        """Return the existing markdown notes, newest first. Never includes `.trash/`
        (a subdirectory, not a `.md` entry at this level) or a symlink."""
        if not os.path.isdir(self.directory):
            return []
        names = []
        for name in os.listdir(self.directory):
            if not name.endswith(".md"):
                continue
            full = os.path.join(self.directory, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            names.append(name)
        return sorted(names, reverse=True)

    def read(self, filename: str) -> str:
        """Read one repository-owned note; reject paths outside the directory."""
        path = self._safe_path(filename)
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def revision(self, filename: str) -> str:
        """Return a cheap content revision for conflict-safe browser sync."""
        path = self._safe_path(filename)
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def write(self, filename: str, note: str, expected_revision: str = "") -> str:
        """Update one existing note without allowing path traversal."""
        path = self._safe_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        if expected_revision and self.revision(filename) != expected_revision:
            raise FileExistsError("note changed since it was opened")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(note if note.endswith("\n") else f"{note}\n")
        return self.revision(filename)

    def rename(self, filename: str, new_filename: str, expected_revision: str = "") -> str:
        """Rename one existing note. Preconditioned on its current revision, same as
        `write`, so a rename can never silently discard a concurrent edit; the new
        name must not already exist. Renaming to a name with a leading `NN-` slug
        token is how a note is recategorized -- there is no separate category field."""
        path = self._safe_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        if expected_revision and self.revision(filename) != expected_revision:
            raise FileExistsError("note changed since it was opened")
        new_path = self._safe_path(new_filename)
        if os.path.exists(new_path) or os.path.islink(new_path):
            raise NoteNameConflictError(new_filename)
        os.rename(path, new_path)
        return self.revision(new_filename)

    def delete(self, filename: str, expected_revision: str = "") -> str:
        """Soft-delete: move the note into `.trash/` inside the same directory
        rather than unlinking it, so `restore` can always bring it back.
        Preconditioned on its current revision, same as `write`."""
        path = self._safe_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        if expected_revision and self.revision(filename) != expected_revision:
            raise FileExistsError("note changed since it was opened")
        trash_dir = self._trash_dir()
        os.makedirs(trash_dir, exist_ok=True)
        prefix = self._now().strftime("%Y%m%d%H%M%S")
        candidate = f"{prefix}_{filename}"
        trashed_path = os.path.join(trash_dir, candidate)
        counter = 2
        while os.path.exists(trashed_path):
            candidate = f"{prefix}_{counter}_{filename}"
            trashed_path = os.path.join(trash_dir, candidate)
            counter += 1
        os.rename(path, trashed_path)
        return candidate

    def list_trash(self):
        """Return trashed filenames, newest-deleted first."""
        trash_dir = self._trash_dir()
        if not os.path.isdir(trash_dir):
            return []
        names = []
        for name in os.listdir(trash_dir):
            full = os.path.join(trash_dir, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            names.append(name)
        return sorted(names, reverse=True)

    def restore(self, trashed_name: str, restored_filename: str = "") -> str:
        """Move a trashed file back into the live notes directory, restoring its
        original name unless `restored_filename` says otherwise (e.g. the
        original name is now taken by an unrelated note). Refuses to overwrite
        an existing note."""
        trash_dir = self._trash_dir()
        trashed_path = self._safe_path(trashed_name, base_dir=trash_dir)
        if not os.path.isfile(trashed_path):
            raise FileNotFoundError(trashed_name)
        target_name = restored_filename or _original_name_from_trash(trashed_name)
        target_path = self._safe_path(target_name)
        if os.path.exists(target_path) or os.path.islink(target_path):
            raise NoteNameConflictError(target_name)
        os.rename(trashed_path, target_path)
        return target_name


def build_note_repository(directory=None) -> NoteRepository:
    return FilesystemNoteRepository(directory)
