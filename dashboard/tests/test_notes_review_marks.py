import json
import shutil
import subprocess
from pathlib import Path

import pytest

import notes_review_marks as marks

DEED = "2026-11-03_draft-personal-representative-s-deed-of-distribution.md"
FIXTURE = "\n".join([
    "# Personal Representative's Deed of Distribution",
    "> This is a DRAFT. Items in [brackets] are not verified.",
    "",
    "- Prepared by: [NOT VERIFIED]",
    "- Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507",
    "conveys and distributes to [GRANTEE NAME(S) — NOT VERIFIED], Grantee,",
    "conveys and distributes to Louis Herbert Adams Jr., whose address is 511 Prince Street SE, Grantee,",
    "Parcel No. [VERIFY]",
    "Transfer tax exemption: [NOT VERIFIED — citations]",
    "Dated: [____________]",
    "Consideration: [NOT VERIFIED — typically none]",
    "```mermaid",
    "graph TD; A[VERIFY]-->B",
    "```",
    "[VERIFY: basis of distribution]",
])


def test_only_the_deed_has_review_marks():
    assert marks.review_marks("2026-11-03_test-one.md", FIXTURE) == []
    assert marks.review_marks(DEED, "just a note [NOT VERIFIED]") == []


def test_marks_carry_line_kind_and_text():
    found = {m["line"]: m for m in marks.review_marks(DEED, FIXTURE)}
    assert found[4]["kind"] == "preparer" and found[4]["text"] == "Prepared by: [NOT VERIFIED]"
    assert 5 not in found and 7 not in found and 10 not in found and 2 not in found
    assert found[8]["kind"] == "legal-description"
    assert found[9]["kind"] == "tax-language"
    assert found[6]["kind"] == found[11]["kind"] == found[15]["kind"] == "open-item"
    assert 13 not in found  # inside a mermaid block


@pytest.mark.skipif(shutil.which("bun") is None, reason="bun is needed to run the browser's own rule")
def test_python_port_agrees_with_the_browsers_rule():
    root = Path(__file__).resolve().parents[1]
    script = ("import { markdownHtml } from './js/boot/notes.js';"
              "const html = markdownHtml(JSON.parse(process.argv[1]).s, { filename: JSON.parse(process.argv[1]).f });"
              "console.log(JSON.stringify([...html.matchAll(/notes-deed-review-([a-z-]+)/g)].map(m => m[1])));")
    out = subprocess.run(["bun", "-e", script, json.dumps({"s": FIXTURE, "f": DEED})],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [m["kind"] for m in marks.review_marks(DEED, FIXTURE)]
