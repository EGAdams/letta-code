import io
import zipfile
from xml.etree import ElementTree

from notes_docx_export import build_docx_bytes

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _document(note_text: str) -> ElementTree.Element:
    data = build_docx_bytes(note_text)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert set(archive.namelist()) >= {
            "[Content_Types].xml", "_rels/.rels",
            "word/_rels/document.xml.rels", "word/styles.xml", "word/document.xml",
        }
        document_xml = archive.read("word/document.xml")
    return ElementTree.fromstring(document_xml)


def _runs(paragraph):
    return paragraph.findall(f"{W}r")


def _run_text(run) -> str:
    return "".join(t.text or "" for t in run.findall(f"{W}t"))


def test_zip_contains_the_minimum_valid_docx_parts():
    _document("hello")  # the assertion is inside the helper


def test_plain_paragraph_round_trips():
    document = _document("hello world")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    [run] = _runs(paragraph)
    assert _run_text(run) == "hello world"


def test_heading_gets_a_heading_style_and_no_hash_marks():
    document = _document("## Section Two")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    assert style.get(f"{W}val") == "Heading2"
    assert _run_text(_runs(paragraph)[0]) == "Section Two"


def test_bullet_line_is_prefixed_and_not_the_raw_dash():
    document = _document("- first item")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    text = _run_text(_runs(paragraph)[0])
    assert text.startswith("•")
    assert "first item" in text
    assert not text.startswith("-")


def test_bold_text_gets_a_bold_run_property():
    document = _document("**important**")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    [run] = _runs(paragraph)
    assert run.find(f"{W}rPr/{W}b") is not None
    assert _run_text(run) == "important"


def test_color_span_sets_the_run_color_to_the_palette_hex():
    document = _document("{{color:red}}warning{{/color}}")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    [run] = _runs(paragraph)
    color = run.find(f"{W}rPr/{W}color")
    assert color.get(f"{W}val") == "C0392B"


def test_highlight_span_maps_to_a_word_highlight_enum_value():
    document = _document("{{highlight:yellow}}note{{/highlight}}")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    [run] = _runs(paragraph)
    highlight = run.find(f"{W}rPr/{W}highlight")
    assert highlight.get(f"{W}val") == "yellow"


def test_blank_line_becomes_an_empty_paragraph():
    document = _document("first\n\nsecond")
    paragraphs = document.find(f"{W}body").findall(f"{W}p")
    assert len(paragraphs) == 3
    assert _runs(paragraphs[1]) == []


def test_special_characters_are_xml_escaped():
    document = _document("A & B < C")
    [paragraph] = document.find(f"{W}body").findall(f"{W}p")
    assert _run_text(_runs(paragraph)[0]) == "A & B < C"
    raw = ElementTree.tostring(paragraph)
    assert b"A &amp; B &lt; C" in raw
