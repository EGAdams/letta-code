"""Note text -> a minimal, valid .docx -- no python-docx dependency.

A .docx is a zip of OOXML parts; Word opens one built from just
[Content_Types].xml, _rels/.rels and word/document.xml (plus styles.xml for
heading/default styles here). Writing that zip directly with the stdlib
keeps this stdlib-only, like the rest of the dashboard backend, and avoids
depending on a package that is not provisioned on every host that runs
server.py.

Formatting comes from notes_formatting.parse_segments, the same parser the
browser preview and the email draft use -- bold/italic/code become run
properties, and a color/highlight span becomes a run color or a highlight
from Word's fixed highlight enum (ST_HighlightColor), the closest name to
each entry in notes_formatting.COLORS.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

import notes_formatting

_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")

#: Word's <w:highlight> only accepts this fixed set of names; map each of
#: notes_formatting.COLORS to its closest member rather than inventing one.
_HIGHLIGHT = {
    "red": "red", "orange": "darkYellow", "yellow": "yellow", "green": "green",
    "blue": "cyan", "purple": "magenta", "gray": "lightGray", "black": "black",
}

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>'
)
_PACKAGE_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type='
    '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    '</Relationships>'
)
_DOCUMENT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type='
    '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/>'
    '</Relationships>'
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
    '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
    '</w:styles>'
)
_DOCUMENT_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body>{body}<w:sectPr/></w:body></w:document>'
)


def _run_xml(segment: notes_formatting.Segment) -> str:
    props = []
    if segment.bold:
        props.append("<w:b/>")
    if segment.italic:
        props.append("<w:i/>")
    if segment.code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
    if segment.color:
        props.append(f'<w:color w:val="{notes_formatting.COLORS[segment.color]}"/>')
    if segment.highlight:
        props.append(f'<w:highlight w:val="{_HIGHLIGHT[segment.highlight]}"/>')
    run_properties = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    text = escape(segment.text)
    return f'<w:r>{run_properties}<w:t xml:space="preserve">{text}</w:t></w:r>'


def _paragraph_xml(text: str, style: str | None = None) -> str:
    runs = "".join(_run_xml(segment) for segment in notes_formatting.parse_segments(text))
    paragraph_properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{paragraph_properties}{runs}</w:p>"


def _body_xml(note_text: str) -> str:
    paragraphs = []
    for line in note_text.splitlines() or [""]:
        heading = _HEADING.match(line)
        bullet = _BULLET.match(line)
        if not line.strip():
            paragraphs.append("<w:p/>")
        elif heading:
            level = min(len(heading.group(1)), 2)
            paragraphs.append(_paragraph_xml(heading.group(2), style=f"Heading{level}"))
        elif bullet:
            paragraphs.append(_paragraph_xml(f"•  {bullet.group(1)}"))
        else:
            paragraphs.append(_paragraph_xml(line))
    return "".join(paragraphs)


def build_docx_bytes(note_text: str) -> bytes:
    """Render one note's Markdown + color markup as a minimal .docx."""
    document_xml = _DOCUMENT_TEMPLATE.format(body=_body_xml(note_text))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _PACKAGE_RELS)
        archive.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        archive.writestr("word/styles.xml", _STYLES)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()
