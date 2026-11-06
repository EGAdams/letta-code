#!/usr/bin/env python3
"""Command-line adapter a ChatGPT Bridge task runs to operate on dashboard
notes through NotesBridgeClient (see ../notes_bridge_client.py).

Every subcommand prints exactly one JSON object to stdout and sets the
process exit code; nothing else is written to stdout or stderr, so a caller
never has to scrape prose for a result and the note text itself is never
written anywhere but that one JSON object. The bearer token
(NOTES_BRIDGE_TOKEN) is never printed or included in any output.

Subcommands:
    list                                         -> {"ok": true, "notes": [...]}
    read <filename>                              -> {"ok": true, "filename", "note", "revision"}
    create                                        (note text on stdin)
                                                  -> {"ok": true, "filename", "revision", "verified"}
    update <filename> --expected-revision REV     (note text on stdin)
                                                  -> {"ok": true, "filename", "revision", "verified"}
    remove-text <filename> --expected-revision REV (exact text to delete on stdin)
                                                  -> {"ok": true, "filename", "revision", "removed"}
    export-docx <filename> <output-path>          -> {"ok": true, "filename", "path", "bytes"}
    email-draft <filename>                        -> {"ok": true, "filename", "subject",
                                                       "body_text", "mailto_url"}
    highlights <filename>                         -> {"ok": true, "filename", "highlights"}

`export-docx` and `email-draft` are both read-only: the first writes the
rendered Word document to the given local path (not back to the dashboard),
the second only returns text. Neither can send mail or touch the note.

`highlights` is also read-only: it returns every persisted
``{{highlight:name}}`` span in the note -- text, color, line, character
offsets, and surrounding context -- recomputed fresh from the note's current
saved text (see ../notes_highlights.py), never a stored range that could
drift from it across a save/reopen. It never reports the Personal
Representative's Deed page's view-only "review" marks (js/boot/notes.js),
which are not saved markup, and has no way to see a browser's current
unsaved text selection.

`create` always assigns a new filename (the repository never overwrites an
existing note that way); `update` and `remove-text` both require
--expected-revision, so there is no code path here that can silently clobber
someone else's edit -- a stale or missing revision is a 428/409 from the
server, surfaced as {"ok": false, "error": ...} and exit code 1, not a retry.
A missing NOTES_BRIDGE_TOKEN fails closed before any request is sent (exit
code 2).

`remove-text` deletes one exact, unique occurrence of the stdin text (e.g. a
single bracketed placeholder) rather than requiring the caller to retype the
whole note -- a narrower edit than `update` for a single deletion, with less
room to accidentally change unrelated text. A single trailing newline from
stdin (as `echo` adds) is stripped before matching; use `printf '%s'` if the
text to remove itself must keep a trailing newline. If the text is missing or
appears more than once, the server is never called and the command reports
{"ok": false, "error": "NoteTextMatchError", ...} with exit code 1.

IMPORTANT LIMITATION: this script only talks to a dashboard that already
exposes /api/notes-bridge/v1 with a provisioned client token (see
docs/notes.md). Registering it as a StarTrekBridge "notes" capability in the
gateway host is a separate, out-of-repo step this script does not perform.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notes_bridge_client as nbc


def _read_stdin() -> str:
    return sys.stdin.read()


def _persisted_text(note: str) -> str:
    return note if note.endswith("\n") else f"{note}\n"


def _cmd_list(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    return {"ok": True, "notes": client.list_notes()}


def _cmd_read(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    note, revision = client.read(args.filename)
    return {"ok": True, "filename": args.filename, "note": note, "revision": revision}


def _cmd_create(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    note = _read_stdin()
    filename, persisted_note, revision = client.create_and_verify(note)
    return {"ok": True, "filename": filename, "revision": revision,
            "verified": persisted_note == _persisted_text(note)}


def _cmd_update(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    note = _read_stdin()
    persisted_note, revision = client.write_and_verify(args.filename, note, args.expected_revision)
    return {"ok": True, "filename": args.filename, "revision": revision,
            "verified": persisted_note == _persisted_text(note)}


def _cmd_remove_text(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    text = _read_stdin()
    if text.endswith("\n"):
        text = text[:-1]
    persisted_note, revision = client.remove_text_and_verify(args.filename, text, args.expected_revision)
    return {"ok": True, "filename": args.filename, "revision": revision,
            "removed": text not in persisted_note}


def _cmd_export_docx(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    data = client.export_docx(args.filename)
    Path(args.output_path).write_bytes(data)
    return {"ok": True, "filename": args.filename, "path": args.output_path, "bytes": len(data)}


def _cmd_email_draft(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    draft = client.email_draft(args.filename)
    return {"ok": True, "filename": args.filename, **draft}


def _cmd_highlights(client: nbc.NotesBridgeClient, args: argparse.Namespace) -> dict:
    highlights = client.highlights(args.filename)
    return {"ok": True, "filename": args.filename, "highlights": highlights}


_HANDLERS = {
    "list": _cmd_list,
    "read": _cmd_read,
    "create": _cmd_create,
    "update": _cmd_update,
    "remove-text": _cmd_remove_text,
    "export-docx": _cmd_export_docx,
    "email-draft": _cmd_email_draft,
    "highlights": _cmd_highlights,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=None,
                         help="Defaults to NOTES_BRIDGE_BASE_URL or http://127.0.0.1:8765.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List note filenames.")

    read_parser = subparsers.add_parser("read", help="Read one note.")
    read_parser.add_argument("filename")

    subparsers.add_parser("create", help="Create a note from stdin.")

    update_parser = subparsers.add_parser("update", help="Update one note from stdin.")
    update_parser.add_argument("filename")
    update_parser.add_argument("--expected-revision", required=True,
                                help="Revision returned by a prior read; a stale or missing "
                                     "value is rejected rather than silently overwritten.")

    remove_text_parser = subparsers.add_parser(
        "remove-text", help="Delete one exact, unique occurrence of stdin text from a note.")
    remove_text_parser.add_argument("filename")
    remove_text_parser.add_argument("--expected-revision", required=True,
                                     help="Revision returned by a prior read; a stale or missing "
                                          "value is rejected rather than silently overwritten.")

    highlights_parser = subparsers.add_parser(
        "highlights", help="List persisted {{highlight:name}} spans in one note. Read-only.")
    highlights_parser.add_argument("filename")

    return parser


def _error_payload(exc: nbc.NotesBridgeError) -> dict:
    payload = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, nbc.NoteConflictError):
        payload["revision"] = exc.revision
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        client = nbc.NotesBridgeClient(base_url=args.base_url)
    except nbc.NotesBridgeConfigError as exc:
        print(json.dumps(_error_payload(exc)))
        return 2

    try:
        result = _HANDLERS[args.command](client, args)
    except nbc.NotesBridgeError as exc:
        print(json.dumps(_error_payload(exc)))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
