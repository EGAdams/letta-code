"""Every-note management for the Bridge: search, create, rename/move, trash, restore, purge.

``notes_bridge.py`` routes to this; it is the one place that touches ``NOTES_DIR``
for anything beyond read/overwrite of an existing file.

* **Storage stays flat.** One ``<date>_<slug>.md`` per note. A *category* is only the leading
  ``NN-`` token of the slug (``2026-11-05_04-probate-deed.md`` is category 04), exactly as the
  browser's Notes list groups them (``js/boot/notes.js``). Moving a note to another category is
  therefore a rename; its text is never touched.
* **Trash is recoverable.** Deleting moves the file to ``NOTES_DIR/.trash/<stamp>__<filename>`` --
  a dot-directory the browser's ``/api/notes`` listing (``*.md`` in the top level) never shows.
  Restore moves it back. Only ``purge`` removes bytes, and only from the trash, and only with the
  exact authorization phrase naming that item (see ``purge_phrase``).
* **No blind change.** rename/trash carry the revision a read returned; a stale one raises
  ``FileExistsError`` and nothing moves. Nothing here ever overwrites an existing note.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
from pathlib import Path

from voice import config
from voice.note_repository import slugify

CATEGORIES = {
    1: "Scoreboard Development", 2: "Finance & Bookkeeping", 3: "Tax Preparation",
    4: "Probate & Real Estate", 5: "AI Agents", 6: "Star Trek Bridge & ADW",
    7: "Dashboards & Web Interfaces", 8: "Document Automation",
    9: "Computer Systems & Networking", 10: "Other Engineering Projects",
}
TRASH_DIR = ".trash"
_NOTE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<stem>[a-z0-9][a-z0-9-]*)\.md$")
_CATEGORY = re.compile(r"^(?P<n>\d{2})-")
_TRASHED = re.compile(r"^(?P<stamp>\d{8}T\d{6}Z)__(?P<name>.+\.md)$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.md$")
MAX_NAME_STEM = 60


class NoteRefused(ValueError):
    """The request is not allowed or not understood (bad name, bad category, wrong phrase...)."""


def purge_phrase(trash_id: str) -> str:
    """The exact sentence that authorizes permanently deleting one trashed note."""
    return f"EG authorizes permanently deleting {trash_id}"


def category_of(filename: str) -> int | None:
    match = _NOTE.match(filename)
    found = _CATEGORY.match(match.group("stem")) if match else None
    return int(found.group("n")) if found and int(found.group("n")) in CATEGORIES else None


class NoteLibrary:
    def __init__(self, directory: str | None = None, clock=None) -> None:
        self.directory = Path(directory or config.NOTES_DIR)
        self._now = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))

    # -- paths ------------------------------------------------------------------
    @property
    def _trash(self) -> Path:
        return self.directory / TRASH_DIR

    def _note_path(self, filename: str) -> Path:
        if not _SAFE_NAME.match(filename or "") or filename.startswith("."):
            raise NoteRefused("invalid note filename")
        return self.directory / filename

    def _trash_path(self, trash_id: str) -> Path:
        if not _TRASHED.match(trash_id or ""):
            raise NoteRefused("invalid trash id")
        return self._trash / trash_id

    @staticmethod
    def _revision(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    # -- list / search ------------------------------------------------------------
    def entry(self, path: Path) -> dict:
        stat = path.stat()
        return {"filename": path.name, "revision": self._revision(path), "bytes": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "category": category_of(path.name),
                "category_name": CATEGORIES.get(category_of(path.name) or 0)}

    def list_all(self, query: str = "", category: int | None = None) -> list[dict]:
        """Every note, newest first; optionally those whose name or text contains ``query``."""
        if not self.directory.is_dir():
            return []
        needle = query.strip().lower()
        out = []
        for path in sorted((p for p in self.directory.iterdir() if p.is_file() and p.suffix == ".md"),
                           key=lambda p: p.name, reverse=True):
            item = self.entry(path)
            if category is not None and item["category"] != category:
                continue
            if needle:
                hits = self._matching_lines(path, needle)
                if needle not in path.name.lower() and not hits:
                    continue
                item["matches"] = hits[:5]
            out.append(item)
        return out

    @staticmethod
    def _matching_lines(path: Path, needle: str) -> list[dict]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return []
        return [{"line": n, "text": line.strip()[:200]} for n, line in enumerate(lines, 1)
                if needle in line.lower()]

    # -- create -------------------------------------------------------------------
    def create(self, name: str, text: str, category: int | None = None) -> dict:
        stem = slugify(name)
        if not stem:
            raise NoteRefused("a note needs a name with letters or digits in it")
        if category is not None:
            if category not in CATEGORIES:
                raise NoteRefused("category must be 1-10")
            stem = f"{category:02d}-{stem}"[:MAX_NAME_STEM].strip("-")
        if not str(text).strip():
            raise NoteRefused("note must not be blank")
        self.directory.mkdir(parents=True, exist_ok=True)
        prefix = self._now().astimezone().strftime("%Y-%m-%d")
        candidate, counter = f"{prefix}_{stem}.md", 2
        while True:
            path = self.directory / candidate
            try:
                with open(path, "x", encoding="utf-8") as handle:  # never overwrite
                    handle.write(text if text.endswith("\n") else text + "\n")
                break
            except FileExistsError:
                candidate, counter = f"{prefix}_{stem}-{counter}.md", counter + 1
        return self.entry(path)

    # -- rename / move --------------------------------------------------------------
    def rename(self, filename: str, expected_revision: str, new_name: str | None = None,
               category: int | None = None, clear_category: bool = False) -> dict:
        """Change a note's name and/or category. Text and date prefix are kept."""
        path = self._note_path(filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        if self._revision(path) != expected_revision:
            raise FileExistsError("note changed since it was read")
        match = _NOTE.match(filename)
        if not match:
            raise NoteRefused("only dated <date>_<name>.md notes can be renamed or moved")
        stem = match.group("stem")
        found = _CATEGORY.match(stem)
        current_cat = int(found.group("n")) if found and int(found.group("n")) in CATEGORIES else None
        base = stem[found.end():] if current_cat is not None else stem
        if new_name is not None:
            base = slugify(new_name)
            if not base:
                raise NoteRefused("a note needs a name with letters or digits in it")
        if category is not None and category not in CATEGORIES:
            raise NoteRefused("category must be 1-10")
        target_cat = None if clear_category else (category if category is not None else current_cat)
        new_stem = f"{target_cat:02d}-{base}" if target_cat is not None else base
        new_stem = new_stem[:MAX_NAME_STEM].strip("-")
        new_filename = f"{match.group('date')}_{new_stem}.md"
        if new_filename == filename:
            return {**self.entry(path), "renamed_from": filename, "changed": False}
        target = self._note_path(new_filename)
        if target.exists():
            raise NoteRefused(f"{new_filename} already exists; pick another name")
        os.link(path, target)  # fails if target exists: no overwrite, even in a race
        os.unlink(path)
        return {**self.entry(target), "renamed_from": filename, "changed": True}

    # -- trash / restore / purge ------------------------------------------------------
    def trash(self, filename: str, expected_revision: str) -> dict:
        path = self._note_path(filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        revision = self._revision(path)
        if revision != expected_revision:
            raise FileExistsError("note changed since it was read")
        self._trash.mkdir(parents=True, exist_ok=True)
        trash_id = f"{self._now().strftime('%Y%m%dT%H%M%SZ')}__{filename}"
        target = self._trash / trash_id
        counter = 2
        while target.exists():
            trash_id = f"{self._now().strftime('%Y%m%dT%H%M%SZ')}__{counter}-{filename}"
            target, counter = self._trash / trash_id, counter + 1
        os.link(path, target)
        os.unlink(path)
        return {"trash_id": trash_id, "filename": filename, "revision": revision}

    def list_trash(self) -> list[dict]:
        if not self._trash.is_dir():
            return []
        out = []
        for path in sorted(self._trash.iterdir(), reverse=True):
            match = _TRASHED.match(path.name)
            if match and path.is_file():
                out.append({"trash_id": path.name, "filename": self._original_name(match.group("name")),
                            "revision": self._revision(path), "bytes": path.stat().st_size,
                            "trashed_at": match.group("stamp")})
        return out

    @staticmethod
    def _original_name(stored: str) -> str:
        return re.sub(r"^\d+-(?=\d{4}-\d{2}-\d{2}_)", "", stored)

    def restore(self, trash_id: str) -> dict:
        source = self._trash_path(trash_id)
        if not source.is_file():
            raise FileNotFoundError(trash_id)
        name = self._original_name(_TRASHED.match(trash_id).group("name"))
        target, counter = self._note_path(name), 2
        while target.exists():  # the name was reused since: keep both, never overwrite
            target = self._note_path(f"{name[:-3]}-restored{'' if counter == 2 else counter}.md")
            counter += 1
        os.link(source, target)
        os.unlink(source)
        return {**self.entry(target), "restored_from": trash_id}

    def purge(self, trash_id: str, authorization: str) -> dict:
        """Permanently delete one *trashed* note, only with the exact phrase naming it."""
        source = self._trash_path(trash_id)
        if authorization != purge_phrase(trash_id):
            raise PermissionError(f'permanent deletion needs authorization: "{purge_phrase(trash_id)}"')
        if not source.is_file():
            raise FileNotFoundError(trash_id)
        revision = self._revision(source)
        source.unlink()
        return {"trash_id": trash_id, "revision": revision, "purged": True}
