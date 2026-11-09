"""Search and permanent delete for notes_bridge.py -- the two things the create/rename/delete/restore handlers
in ``notes_bridge_notes.py`` do not do. Same ``(status, payload, event, log_fields)`` shape as those handlers,
so ``dispatch`` keeps one logging call site.

* **search** -- ``GET /notes?q=text&category=N`` lists the in-scope notes whose name or text contains ``q``
  (matching lines returned) and/or whose filename carries category ``N``. A category is only the leading ``NN-``
  token of the filename's slug (``2026-11-05_04-deed.md`` is category 04), exactly as the browser's Notes list
  groups them, so "move to another category" is an ordinary rename. Without ``q``/``category`` the plain list is
  unchanged. Revisions are included so an agent can detect that a note was changed elsewhere.
* **purge** -- ``POST /trash/<trashed_name>/purge`` removes bytes. It is the only call that does, and it works
  only on a file already in ``.trash/`` and only when the body carries the exact sentence
  ``purge_phrase(trashed_name)``. Anything else is a 403 and nothing is deleted.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import parse_qs

CATEGORIES = {
    1: "Scoreboard Development", 2: "Finance & Bookkeeping", 3: "Tax Preparation",
    4: "Probate & Real Estate", 5: "AI Agents", 6: "Star Trek Bridge & ADW",
    7: "Dashboards & Web Interfaces", 8: "Document Automation",
    9: "Computer Systems & Networking", 10: "Other Engineering Projects",
}
_CATEGORY = re.compile(r"^\d{4}-\d{2}-\d{2}_(\d{2})-")
_TRASHED = re.compile(r"^\d{14}_(?:\d+_)?[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.md$")
TRASH_DIRNAME = ".trash"


def category_of(filename: str) -> int | None:
    found = _CATEGORY.match(filename)
    number = int(found.group(1)) if found else 0
    return number if number in CATEGORIES else None


def purge_phrase(trashed_name: str) -> str:
    """The exact sentence that authorizes permanently deleting one trashed note."""
    return f"EG authorizes permanently deleting {trashed_name}"


def wants_search(query_string: str) -> bool:
    return any(key in parse_qs(query_string) for key in ("q", "category", "detail"))


def search(repository, approved: "frozenset[str] | None", query_string: str):
    params = parse_qs(query_string)
    needle = params.get("q", [""])[0].strip().lower()
    raw_category = params.get("category", [""])[0]
    try:
        category = int(raw_category) if raw_category else None
    except ValueError:
        return (400, {"error": "category must be a number 1-10"}, "error", {"detail": "bad category"})
    entries = []
    for name in repository.list():
        if approved is not None and name not in approved:
            continue
        if category is not None and category_of(name) != category:
            continue
        matches = _matching_lines(repository, name, needle) if needle else []
        if needle and needle not in name.lower() and not matches:
            continue
        number = category_of(name)
        entry = {"filename": name, "revision": repository.revision(name), "category": number,
                 "category_name": CATEGORIES.get(number or 0)}
        if needle:
            entry["matches"] = matches[:5]
        entries.append(entry)
    names = [e["filename"] for e in entries]
    return (200, {"ok": True, "notes": names, "entries": entries}, "list",
            {"detail": f"search: {len(names)} note(s)"})


def _matching_lines(repository, name: str, needle: str) -> list[dict]:
    try:
        lines = repository.read(name).splitlines()
    except (OSError, ValueError):
        return []
    return [{"line": n, "text": line.strip()[:200]} for n, line in enumerate(lines, 1) if needle in line.lower()]


def purge(repository, trashed_name: str, body: bytes):
    data = json.loads(body or b"{}")
    authorization = data.get("authorization", "")
    if not isinstance(authorization, str):
        return (400, {"error": "authorization must be a string"},
                "error", {"filename": trashed_name, "detail": "bad purge body"})
    if not _TRASHED.match(trashed_name or ""):
        return (400, {"error": "refused", "message": "only a note already in the trash can be purged"},
                "refused", {"filename": trashed_name, "detail": "purge of something that is not a trashed note"})
    if authorization != purge_phrase(trashed_name):
        return (403, {"error": "authorization_required",
                      "message": f'permanent deletion needs authorization: "{purge_phrase(trashed_name)}"'},
                "refused", {"filename": trashed_name, "detail": "purge without the authorization phrase"})
    trash = os.path.realpath(os.path.join(repository.directory, TRASH_DIRNAME))
    path = os.path.realpath(os.path.join(trash, trashed_name))
    if os.path.dirname(path) != trash or os.path.islink(os.path.join(trash, trashed_name)) or not os.path.isfile(path):
        raise FileNotFoundError(trashed_name)
    os.unlink(path)
    return (200, {"ok": True, "trashed_name": trashed_name, "purged": True},
            "purge", {"filename": trashed_name, "detail": "permanent"})
