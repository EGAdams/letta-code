import json
import shutil
import subprocess
from pathlib import Path

import pytest

import notes_active_warning as active
import notes_bridge

DEED = "2026-11-03_draft-personal-representative-s-deed-of-distribution.md"

PARTIALLY_VERIFIED_WARNING = (
    "[PARTIALLY VERIFIED: the closing statement was filed. Under "
    "[MCL 700.3954(2)](https://example.test/a) the appointment ends a year later. "
    "VERIFY WITH THE PROBATE COURT OR A MICHIGAN ESTATE ATTORNEY: "
    "confirm which recitals are required.]"
)


def test_none_for_an_ordinary_resolved_deed():
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        "The Personal Representative has full authority under the Letters of Authority.",
        "- Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507",
    ])
    assert active.active_warning(DEED, source) is None
    assert active.active_warnings(DEED, source) == []


def test_none_when_the_warning_sentence_sits_outside_the_authority_section():
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Other warnings",
        PARTIALLY_VERIFIED_WARNING,
    ])
    assert active.active_warning(DEED, source) is None


def test_none_for_a_non_deed_note_even_with_the_same_warning_text():
    source = "\n".join([
        "## Authority of the Personal Representative",
        PARTIALLY_VERIFIED_WARNING,
    ])
    assert active.active_warning("meeting-notes.md", source) is None


def test_one_known_deed_with_a_bracketed_partially_verified_warning():
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        PARTIALLY_VERIFIED_WARNING,
        "## Other warnings",
        PARTIALLY_VERIFIED_WARNING,
    ])
    found = active.active_warning(DEED, source)
    assert found == {"line": 3, "text": PARTIALLY_VERIFIED_WARNING}
    # the identical sentence repeated under a different heading is not active --
    # the warning is a static review mark there, not the blinking passage.
    assert active.active_warnings(DEED, source) == [{"line": 3, "text": PARTIALLY_VERIFIED_WARNING}]


def test_static_review_marks_never_count_as_the_active_warning():
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        "- Prepared by: [NOT VERIFIED]",
        "Tax Parcel No.: [VERIFY CURRENT PARCEL NO. WITH CITY ASSESSOR]",
    ])
    assert active.active_warning(DEED, source) is None


def test_explicit_focus_selects_any_exact_unresolved_paragraph_and_hides_marker():
    target = '[VERIFY: the 2017 deed names the grantee "Louis Adams"; confirm the source title.]'
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "<!-- notes-review-focus: " + target + " -->",
        "## Source of title",
        target,
        "## Authority of the Personal Representative",
        "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: this remains still.]",
    ])
    assert active.active_warning(DEED, source) == {"line": 4, "text": target}
    assert active.active_warnings(DEED, source) == [{"line": 4, "text": target}]


def test_explicit_focus_no_match_does_not_fall_back_to_legacy_warning():
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "<!-- notes-review-focus: [VERIFY: no longer in this note] -->",
        "## Authority of the Personal Representative",
        "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: do not blink this.]",
    ])
    assert active.active_warning(DEED, source) is None


def test_explicit_duplicate_focus_suppresses_every_pulse():
    target = "[VERIFY: duplicated focus]"
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "<!-- notes-review-focus: " + target + " -->",
        "## Source of title",
        target,
        "## Authority of the Personal Representative",
        target,
    ])
    assert active.active_warning(DEED, source) is None
    assert active.active_warnings(DEED, source) == []


class _Repo:
    def __init__(self, text):
        self.text = text

    def list(self):
        return ["deed.md"]

    def read(self, filename):
        return self.text

    def revision(self, filename):
        return "r1"


class _Auth:
    def authorize(self, client_ip, headers, scope):
        return "agent-bridge-notes"


def test_highlights_route_separates_the_active_line_from_review_marks(monkeypatch, tmp_path):
    approved = tmp_path / "approved.json"
    approved.write_text(json.dumps({"notes": ["deed.md"]}))
    monkeypatch.setenv("NOTES_BRIDGE_APPROVED", str(approved))
    monkeypatch.setenv("NOTES_ACTIVITY_LOG", str(tmp_path / "notes_activity.jsonl"))
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        PARTIALLY_VERIFIED_WARNING,
        "- Prepared by: [NOT VERIFIED]",
    ])
    repo = _Repo(source)
    monkeypatch.setattr(notes_bridge.composition, "authorizer", lambda: _Auth())
    monkeypatch.setattr(notes_bridge.note_repository, "build_note_repository", lambda: repo)
    status, raw = notes_bridge.dispatch(
        "GET", "/api/notes-bridge/v1/notes/deed.md/highlights",
        {"authorization": "Bearer test"}, "127.0.0.1")
    body = json.loads(raw)
    assert status == 200
    # the active warning is reported once, with its line number ...
    assert body["active_warning"] == {"line": 3, "text": PARTIALLY_VERIFIED_WARNING}
    # ... and never duplicated into the static review_marks list, even though
    # notes_review_marks.review_kind alone would also flag that same line.
    assert all(mark["line"] != 3 for mark in body["review_marks"])
    assert [mark["kind"] for mark in body["review_marks"]] == ["preparer"]


@pytest.mark.skipif(shutil.which("bun") is None, reason="bun is needed to run the browser's own rule")
def test_python_port_agrees_with_the_browsers_rule():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join([
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        PARTIALLY_VERIFIED_WARNING,
        "## Other warnings",
        PARTIALLY_VERIFIED_WARNING,
        "- Prepared by: [NOT VERIFIED]",
    ])
    script = (
        "import { markdownHtml } from './js/boot/notes.js';"
        "const html = markdownHtml(JSON.parse(process.argv[1]).s, { filename: JSON.parse(process.argv[1]).f });"
        "console.log(JSON.stringify((html.match(/notes-deed-review-active-line/g) || []).length));"
    )
    out = subprocess.run(
        ["bun", "-e", script, json.dumps({"s": source, "f": DEED})],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    assert json.loads(out) == len(active.active_warnings(DEED, source))
