from notes_highlights import Highlight, extract_highlights, highlights_payload


def test_no_highlight_markup_yields_nothing():
    assert extract_highlights("plain text, no markup here\n") == []


def test_color_span_alone_is_not_a_highlight():
    assert extract_highlights("{{color:red}}warning{{/color}}\n") == []


def test_single_highlight_reports_text_color_and_line():
    note = "line one\n{{highlight:yellow}}verify the legal description{{/highlight}}\nline three\n"
    [highlight] = extract_highlights(note)
    assert highlight.text == "verify the legal description"
    assert highlight.color == "yellow"
    assert highlight.line == 2
    assert note[highlight.start:highlight.end] == "verify the legal description"


def test_multiple_highlights_are_returned_in_document_order():
    note = "{{highlight:yellow}}first{{/highlight}}\n\n{{highlight:green}}second{{/highlight}}\n"
    highlights = extract_highlights(note)
    assert [(h.text, h.color, h.line) for h in highlights] == [
        ("first", "yellow", 1),
        ("second", "green", 3),
    ]


def test_context_captures_surrounding_text():
    note = "Please {{highlight:yellow}}verify this{{/highlight}} before filing.\n"
    [highlight] = extract_highlights(note)
    assert highlight.context_before.endswith("Please ")
    assert highlight.context_after.startswith(" before filing.")


def test_context_near_the_start_of_the_note_does_not_underflow():
    note = "{{highlight:yellow}}verify this{{/highlight}} before filing.\n"
    [highlight] = extract_highlights(note)
    assert highlight.context_before == ""


def test_unknown_color_name_is_not_a_highlight():
    assert extract_highlights("{{highlight:chartreuse}}x{{/highlight}}\n") == []


def test_highlights_payload_is_json_safe_dicts():
    note = "{{highlight:yellow}}verify this{{/highlight}}\n"
    start = note.index("verify this")
    end = start + len("verify this")
    assert highlights_payload(note) == [{
        "text": "verify this", "color": "yellow", "line": 1,
        "start": start, "end": end,
        "context_before": "", "context_after": "",
    }]


def test_highlight_is_a_frozen_dataclass():
    highlight = Highlight(text="x", color="yellow", line=1, start=0, end=1,
                           context_before="", context_after="")
    assert highlight.text == "x"
