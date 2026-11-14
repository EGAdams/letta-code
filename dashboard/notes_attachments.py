"""PDF attachments on notes: the dashboard's own store, and the Bridge handlers over it.

Where they live. ``<notes dir>/.attachments/`` holds one ``<id>.pdf`` per attachment and an ``index.json`` naming
which note each belongs to. It sits beside ``.trash/`` and, like it, is a directory, so the note list never shows
it. The notes directory is outside every repository, so an attachment survives a refresh, a restart and a deploy.

Identity. An attachment id is ``a-`` plus 12 hex of sha256("<note>|<pdf sha256>"): the same PDF attached to the
same note twice is the same attachment (the second attach changes nothing and says so), and the id never depends
on a clock or a counter.

What is refused, before anything is written: a body that is not a PDF (it must start ``%PDF-`` and carry
``%%EOF`` near its end), one over ``MAX_BYTES``, one whose sha256 differs from the one declared, an id or note
name that is not exactly the expected shape, a note that does not exist, and (in ``notes_bridge``) a protected
or out-of-scope note. A note's own text is never read or written here: attaching changes nothing in the
Markdown, its highlights or its review state.

Removal is soft. ``remove`` marks the entry removed and moves the PDF into ``.attachments/.removed/``, so a
removal can be undone by attaching the same bytes again.

Handlers return ``(status, payload, event, log_fields)`` like ``notes_bridge_notes``.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import fcntl
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

DIRNAME = ".attachments"
REMOVED_DIRNAME = ".removed"
MAX_BYTES = 10 * 1024 * 1024
MAX_TITLE = 120
_ID = re.compile(r"^a-[0-9a-f]{12}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_NOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.md$")
_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


class AttachmentRefused(ValueError):
    """A request the store will not carry out; ``code`` is the error the caller sees."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def attachment_id(note: str, sha256: str) -> str:
    return "a-" + hashlib.sha256(f"{note}|{sha256}".encode()).hexdigest()[:12]


def check_pdf(data: bytes) -> None:
    """Raise AttachmentRefused unless ``data`` is plausibly one whole PDF within the size limit."""
    if not data:
        raise AttachmentRefused("empty", "the file is empty")
    if len(data) > MAX_BYTES:
        raise AttachmentRefused("too_large", f"the file is {len(data)} bytes; the limit is {MAX_BYTES}")
    if not data.startswith(b"%PDF-"):
        raise AttachmentRefused("not_a_pdf", "the file does not start with %PDF-, so it is not a PDF")
    if b"%%EOF" not in data[-2048:]:
        raise AttachmentRefused("not_a_pdf", "the file has no %%EOF near its end; it is cut short or not a PDF")


def page_count(data: bytes) -> int:
    """A best-effort count of /Type /Page objects; 0 when the PDF hides them (object streams)."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def safe_name(name: str, fallback: str) -> str:
    cleaned = _NAME_UNSAFE.sub("_", os.path.basename(str(name or ""))).strip(" .")[:120]
    if not cleaned.lower().endswith(".pdf"):
        cleaned = (cleaned or fallback.removesuffix(".pdf")) + ".pdf"
    return cleaned


class AttachmentStore:
    """The ``.attachments`` folder of one notes directory. Every change holds an exclusive lock on the index."""

    def __init__(self, notes_dir: str) -> None:
        self.notes_dir = os.path.realpath(notes_dir)
        self.root = os.path.join(self.notes_dir, DIRNAME)

    # ---- reads -------------------------------------------------------------------------------------------

    def list(self, note: str) -> list[dict]:
        self._check_note(note)
        return [self._public(e) for e in self._entries() if e["note"] == note and not e.get("removed")]

    def get(self, note: str, attachment: str) -> dict:
        entry = self._find(note, attachment)
        data = self._read_bytes(attachment)
        actual = hashlib.sha256(data).hexdigest()
        return {**self._public(entry), "sha256_on_disk": actual, "intact": actual == entry["sha256"]}

    def content(self, note: str, attachment: str) -> tuple[dict, bytes]:
        entry = self._find(note, attachment)
        data = self._read_bytes(attachment)
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise AttachmentRefused("damaged", "the stored PDF no longer matches its recorded sha256")
        return self._public(entry), data

    def verified_path(self, note: str, attachment: str) -> tuple[dict, str]:
        """Like ``content``, but for a caller (printing) that hands the file to another process rather
        than reading the bytes itself: same integrity check, the on-disk path instead of the bytes."""
        entry, _data = self.content(note, attachment)
        return entry, self._pdf_path(attachment)

    # ---- writes ------------------------------------------------------------------------------------------

    def attach(self, note: str, data: bytes, title: str = "", name: str = "", declared_sha256: str = "",
               task: str = "", actor: str = "") -> tuple[dict, bool]:
        """Store ``data`` on ``note``. Returns (entry, created) -- created False when it was already attached."""
        self._check_note(note)
        check_pdf(data)
        sha = hashlib.sha256(data).hexdigest()
        if declared_sha256 and declared_sha256.lower() != sha:
            raise AttachmentRefused("sha256_mismatch", f"the bytes hash to {sha}, not the declared sha256")
        title = " ".join(str(title or "").split())[:MAX_TITLE]
        ident = attachment_id(note, sha)
        with self._locked():
            entries = self._entries()
            existing = next((e for e in entries if e["id"] == ident), None)
            if existing and not existing.get("removed") and self._intact(ident, sha):
                return self._public(existing), False
            self._write_bytes(ident, data)
            entry = {"id": ident, "note": note, "title": title or safe_name(name, ident),
                     "filename": safe_name(name, ident), "sha256": sha, "bytes": len(data),
                     "pages": page_count(data), "content_type": "application/pdf",
                     "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "added_by": actor, "task_id": task}
            entries = [e for e in entries if e["id"] != ident] + [entry]
            self._save(entries)
            return self._public(entry), True

    def remove(self, note: str, attachment: str, task: str = "", actor: str = "") -> dict:
        with self._locked():
            entries = self._entries()
            entry = self._find(note, attachment, entries)
            source = self._pdf_path(attachment)
            if os.path.isfile(source):
                removed_dir = os.path.join(self.root, REMOVED_DIRNAME)
                os.makedirs(removed_dir, mode=0o700, exist_ok=True)
                os.replace(source, os.path.join(removed_dir, f"{attachment}-{int(time.time())}.pdf"))
            entry.update(removed=True, removed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         removed_by=actor, removed_task_id=task)
            self._save(entries)
            return self._public(entry)

    # ---- internals ---------------------------------------------------------------------------------------

    def _check_note(self, note: str) -> None:
        if not _NOTE.match(note or ""):
            raise AttachmentRefused("bad_note", "not a note file name")
        path = os.path.join(self.notes_dir, note)
        if os.path.islink(path) or not os.path.isfile(path):
            raise FileNotFoundError(note)

    def _find(self, note: str, attachment: str, entries: list[dict] | None = None) -> dict:
        self._check_note(note)
        if not _ID.match(attachment or ""):
            raise AttachmentRefused("bad_attachment_id", "an attachment id is a- followed by 12 hex digits")
        for entry in entries if entries is not None else self._entries():
            if entry["id"] == attachment and entry["note"] == note and not entry.get("removed"):
                return entry
        raise AttachmentRefused("attachment_not_found", f"{note} has no attachment {attachment}")

    def _pdf_path(self, attachment: str) -> str:
        if not _ID.match(attachment):
            raise AttachmentRefused("bad_attachment_id", "an attachment id is a- followed by 12 hex digits")
        return os.path.join(self.root, f"{attachment}.pdf")

    def _intact(self, attachment: str, sha: str) -> bool:
        try:
            return hashlib.sha256(self._read_bytes(attachment)).hexdigest() == sha
        except AttachmentRefused:
            return False

    def _read_bytes(self, attachment: str) -> bytes:
        path = self._pdf_path(attachment)
        if os.path.islink(path) or not os.path.isfile(path):
            raise AttachmentRefused("damaged", "the stored PDF is missing")
        with open(path, "rb") as handle:
            return handle.read(MAX_BYTES + 1)

    def _write_bytes(self, attachment: str, data: bytes) -> None:
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        final = self._pdf_path(attachment)
        temporary = final + ".part"
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final)

    def _entries(self) -> list[dict]:
        try:
            with open(os.path.join(self.root, "index.json"), encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return []
        rows = data.get("attachments") if isinstance(data, dict) else None
        return [r for r in rows or [] if isinstance(r, dict) and _ID.match(str(r.get("id", "")))
                and isinstance(r.get("note"), str) and _SHA.match(str(r.get("sha256", "")))]

    def _save(self, entries: list[dict]) -> None:
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        final = os.path.join(self.root, "index.json")
        temporary = final + ".part"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "attachments": entries}, handle, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final)

    @contextlib.contextmanager
    def _locked(self):
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        with open(os.path.join(self.root, ".lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def _public(entry: dict) -> dict:
        keys = ("id", "note", "title", "filename", "sha256", "bytes", "pages", "content_type", "added_at",
                "added_by", "task_id", "removed", "removed_at")
        return {k: entry[k] for k in keys if k in entry}


def resolve_for_print(notes_dir: str, data: dict) -> tuple[str, str]:
    """``(path, title)`` for the printer workflow (monitoring/printer_panel.py). ``data`` must name an
    existing, intact attachment via ``filename``/``attachment``; anything else raises ``LookupError``
    with a message the printer workflow surfaces to the caller unchanged. The PDF's sha256 is
    re-checked against the index right before its path is handed to another process, so a damaged
    file is refused here rather than printed wrong.
    """
    filename, attachment = data.get("filename"), data.get("attachment")
    if not isinstance(filename, str) or not filename or not isinstance(attachment, str) or not attachment:
        raise LookupError("filename and attachment are required.")
    try:
        entry, path = AttachmentStore(notes_dir).verified_path(filename, attachment)
    except (FileNotFoundError, AttachmentRefused) as exc:
        raise LookupError(f"Could not print: {exc}") from exc
    return path, entry["filename"]


# ---- Bridge handlers ( notes_bridge.dispatch calls these after auth, scope and protection checks ) ----------

def _refused(exc: AttachmentRefused, filename: str):
    status = 404 if exc.code == "attachment_not_found" else 413 if exc.code == "too_large" else 400
    if exc.code == "damaged":
        status = 500
    return (status, {"error": exc.code, "message": str(exc)}, "attachment_refused",
            {"filename": filename, "detail": f"{exc.code}: {exc}"})


def bridge_list(store: AttachmentStore, filename: str):
    try:
        rows = store.list(filename)
    except AttachmentRefused as exc:
        return _refused(exc, filename)
    return (200, {"ok": True, "filename": filename, "attachments": rows}, "attachments",
            {"filename": filename, "detail": f"{len(rows)} attachment(s)"})


def bridge_get(store: AttachmentStore, filename: str, attachment: str, with_content: bool):
    try:
        info = store.get(filename, attachment)
        payload = {"ok": True, "filename": filename, "attachment": info}
        if with_content:
            _, data = store.content(filename, attachment)
            payload["pdf_base64"] = base64.b64encode(data).decode("ascii")
    except AttachmentRefused as exc:
        return _refused(exc, filename)
    return (200, payload, "attachment", {"filename": filename,
                                          "detail": f"{attachment} intact={info['intact']} content={with_content}"})


def bridge_attach(store: AttachmentStore, filename: str, body: bytes, task: str, actor: str):
    data = json.loads(body or b"{}")
    encoded = data.get("pdf_base64")
    if not isinstance(encoded, str) or not encoded:
        return (400, {"error": "pdf_base64_required"}, "attachment_refused",
                {"filename": filename, "detail": "no pdf_base64"})
    if len(encoded) > (MAX_BYTES * 4) // 3 + 8:
        return _refused(AttachmentRefused("too_large", f"the file is over {MAX_BYTES} bytes"), filename)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return (400, {"error": "bad_base64"}, "attachment_refused", {"filename": filename, "detail": "bad base64"})
    fields = {k: data.get(k) for k in ("title", "name", "sha256")}
    if any(v is not None and not isinstance(v, str) for v in fields.values()):
        return (400, {"error": "bad_field", "message": "title, name and sha256 are strings"}, "attachment_refused",
                {"filename": filename, "detail": "non-string field"})
    try:
        entry, created = store.attach(filename, raw, fields["title"] or "", fields["name"] or "",
                                      fields["sha256"] or "", task=task, actor=actor)
    except AttachmentRefused as exc:
        return _refused(exc, filename)
    return (201 if created else 200, {"ok": True, "filename": filename, "attachment": entry, "created": created},
            "attach_pdf", {"filename": filename,
                           "detail": f"{entry['id']} {entry['bytes']} bytes sha256 {entry['sha256'][:16]}"
                                     f"{'' if created else ' (already attached)'}"})


def bridge_remove(store: AttachmentStore, filename: str, attachment: str, task: str, actor: str):
    try:
        entry = store.remove(filename, attachment, task=task, actor=actor)
    except AttachmentRefused as exc:
        return _refused(exc, filename)
    return (200, {"ok": True, "filename": filename, "attachment": entry, "removed": True}, "detach_pdf",
            {"filename": filename, "detail": f"{attachment} removed (kept in .attachments/.removed)"})


# ---- browser routes ( the Notes editor's attachment panel; http_app/get_routes.py calls ``serve`` ) -----------

BROWSER_LIST = "/api/notes/attachments"
BROWSER_FILE = "/api/notes/attachment-file"


def serve(notes_dir: str, path: str, query: dict, record) -> tuple[int, bytes, str, tuple]:
    """``(status, body, content type, extra headers)`` for one of the two browser routes.

    ``BROWSER_LIST?filename=<note>`` lists a note's attachments; ``BROWSER_FILE?filename=<note>&id=<id>`` sends
    the PDF itself, inline (View / Print) or with ``download=1`` as a download. The bytes are re-hashed before
    they are sent, so a damaged file is a 500 rather than a wrong document. ``record`` is notes_activity.record.
    """
    store = AttachmentStore(notes_dir)
    filename = (query.get("filename") or [""])[0]
    try:
        if path == BROWSER_LIST:
            rows = store.list(filename)
            return 200, json.dumps({"ok": True, "filename": filename, "attachments": rows}).encode(), \
                "application/json", ()
        entry, data = store.content(filename, (query.get("id") or [""])[0])
    except FileNotFoundError:
        return 404, b'{"error": "note_not_found"}', "application/json", ()
    except AttachmentRefused as exc:
        status = _refused(exc, filename)[0]
        return status, json.dumps({"error": exc.code, "message": str(exc)}).encode(), "application/json", ()
    download = (query.get("download") or ["0"])[0] == "1"
    record("attachment_download" if download else "attachment_view", filename=filename, actor="browser",
           detail=f"{entry['id']} {entry['bytes']} bytes")
    disposition = "attachment" if download else "inline"
    quoted = entry["filename"].replace('"', "")
    # No CSP sandbox here: Chrome refuses to run its own PDF viewer inside a sandboxed document, so View and
    # Print would show nothing. The bytes were checked to be a PDF and are sent as application/pdf, nosniff.
    return 200, data, "application/pdf", (("Content-Disposition", f'{disposition}; filename="{quoted}"'),
                                          ("X-Content-Type-Options", "nosniff"))
