from notes_formatting import Segment, iter_highlight_spans, parse_segments, plain_text


def test_plain_line_is_one_segment():
    assert parse_segments("hello") == [Segment("hello")]


def test_bold_italic_and_code_are_recognized():
    assert parse_segments("**bold** *italic* `code`") == [
        Segment("bold", bold=True),
        Segment(" "),
        Segment("italic", italic=True),
        Segment(" "),
        Segment("code", code=True),
    ]


def test_color_span_is_recognized():
    assert parse_segments("{{color:red}}warning{{/color}}") == [
        Segment("warning", color="red"),
    ]


def test_highlight_span_is_recognized():
    assert parse_segments("{{highlight:yellow}}note this{{/highlight}}") == [
        Segment("note this", highlight="yellow"),
    ]

def test_color_span_mixed_with_plain_text():
    assert parse_segments("before {{color:blue}}middle{{/color}} after") == [
        Segment("before "),
        Segment("middle", color="blue"),
        Segment(" after"),
    ]


def test_unknown_color_name_renders_as_literal_text():
    segments = parse_segments("{{color:chartreuse}}x{{/color}}")
    assert segments == [Segment("{{color:chartreuse}}x{{/color}}")]


def test_unclosed_span_renders_as_literal_text():
    segments = parse_segments("{{color:red}}never closed")
    assert "".join(s.text for s in segments) == "{{color:red}}never closed"


def test_mismatched_close_tag_renders_as_literal_text():
    segments = parse_segments("{{color:red}}x{{/highlight}}")
    assert "".join(s.text for s in segments) == "{{color:red}}x{{/highlight}}"


def test_color_span_does_not_apply_nested_markdown():
    segments = parse_segments("{{color:red}}**not bold**{{/color}}")
    assert segments == [Segment("**not bold**", color="red")]


def test_plain_text_strips_all_markup_and_keeps_line_breaks():
    note = "# Title\n\n{{color:red}}Warning:{{/color}} **do not skip** this.\n"
    assert plain_text(note) == "# Title\n\nWarning: do not skip this."


def test_plain_text_on_blank_note_is_empty():
    assert plain_text("") == ""


def test_iter_highlight_spans_reports_exact_offsets():
    note = "before {{highlight:yellow}}note this{{/highlight}} after"
    [(color, text, start, end)] = list(iter_highlight_spans(note))
    assert color == "yellow"
    assert text == "note this"
    assert note[start:end] == "note this"


def test_iter_highlight_spans_skips_color_spans():
    note = "{{color:red}}warning{{/color}} {{highlight:green}}go{{/highlight}}"
    spans = list(iter_highlight_spans(note))
    assert [s[0:2] for s in spans] == [("green", "go")]


def test_iter_highlight_spans_skips_unknown_color_name():
    assert list(iter_highlight_spans("{{highlight:chartreuse}}x{{/highlight}}")) == []


def test_iter_highlight_spans_finds_every_occurrence_in_order():
    note = "{{highlight:yellow}}first{{/highlight}} and {{highlight:blue}}second{{/highlight}}"
    spans = list(iter_highlight_spans(note))
    assert [(color, text) for color, text, _, _ in spans] == [("yellow", "first"), ("blue", "second")]
