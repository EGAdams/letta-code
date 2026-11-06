from urllib.parse import parse_qs, urlparse

from notes_email_draft import build_email_draft


def test_subject_comes_from_the_first_heading():
    draft = build_email_draft("deed.md", "# Deed of Distribution\n\nBody text.\n")
    assert draft["subject"] == "Deed of Distribution"


def test_subject_falls_back_to_the_first_nonblank_line():
    draft = build_email_draft("note.md", "\n  first real line\nsecond line\n")
    assert draft["subject"] == "first real line"


def test_subject_falls_back_to_the_filename_when_note_is_blank():
    draft = build_email_draft("empty.md", "\n\n")
    assert draft["subject"] == "empty.md"


def test_body_text_strips_markup():
    draft = build_email_draft(
        "note.md", "{{color:red}}Important:{{/color}} **review** this.\n")
    assert draft["body_text"] == "Important: review this."


def test_mailto_url_carries_subject_and_body_and_no_recipient_by_default():
    draft = build_email_draft("note.md", "Subject line\n\nBody.\n")
    parsed = urlparse(draft["mailto_url"])
    assert parsed.scheme == "mailto"
    assert parsed.path == ""
    query = parse_qs(parsed.query)
    assert query["subject"] == ["Subject line"]
    assert query["body"] == ["Subject line\n\nBody."]


def test_mailto_url_includes_a_recipient_when_given():
    draft = build_email_draft("note.md", "x\n", to="person@example.com")
    assert draft["mailto_url"].startswith("mailto:person%40example.com?")


def test_nothing_here_can_send_a_message():
    import notes_email_draft
    assert not hasattr(notes_email_draft, "send")
    assert not hasattr(notes_email_draft, "smtp")
