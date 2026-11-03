"""Reading a stored scan: page images and text, all on this machine.

Images go through Pillow (EXIF orientation applied, pixel-count capped); PDFs
through PyMuPDF. Every page is turned upright before it is rendered or read:
`tesseract --psm 0` (orientation detection) says how far, and a page it cannot
judge is left as it is. Text comes from a PDF's own text layer when it has one,
else from the local `tesseract` binary. Both tesseract calls use a fixed
argument vector and a timeout. Nothing here is sent anywhere.

A "full" rendition of a JPEG that needs no turning and no shrinking is the
original bytes, so it is never stored twice. The PNG handed to tesseract is
lossless on purpose (better OCR) and lives only in a temp directory.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from typing import Callable

from scan_jobs.models import PageText, RenderedPage

MAX_PDF_PAGES = 50
MAX_IMAGE_PIXELS = 150_000_000
RENDITION_EDGE = {'preview': 1600, 'full': 3400}
OCR_TIMEOUT_SECONDS = 90
OSD_TIMEOUT_SECONDS = 30
OSD_EDGE = 2000                 # orientation needs letters, not every pixel
MIN_OSD_CONFIDENCE = 2.0        # tesseract's own "this is a guess" line
MIN_EMBEDDED_CHARS = 20


class DocumentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


OcrRunner = Callable[[bytes], str]
#: A page's PNG -> degrees to turn it clockwise to stand it upright (0, 90, 180 or 270).
OrientationDetector = Callable[[bytes], int]


def _tesseract(png: bytes, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run tesseract on a temp copy of `png`. Fixed argv; the only variable is that temp file."""
    binary = shutil.which('tesseract')
    if not binary:
        raise DocumentError('ocr_unavailable', 'tesseract is not installed')
    with tempfile.TemporaryDirectory(prefix='scan_ocr_') as tmp:
        src = os.path.join(tmp, 'page.png')
        with open(src, 'wb') as out:
            out.write(png)
        try:
            return subprocess.run([binary, src, 'stdout', *args],
                                  capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise DocumentError('ocr_timeout', 'OCR timed out') from exc


def tesseract_ocr(png: bytes) -> str:
    """Local OCR of a page already standing upright."""
    proc = _tesseract(png, ['-l', 'eng', '--psm', '3'], OCR_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        raise DocumentError('ocr_failed', 'OCR failed')
    return proc.stdout.decode('utf-8', errors='replace')


def tesseract_orientation(png: bytes) -> int:
    """Clockwise degrees that stand the page upright, from tesseract's OSD. Never raises:
    a page with too few letters, a low-confidence guess or a missing binary is 0."""
    try:
        proc = _tesseract(png, ['--psm', '0'], OSD_TIMEOUT_SECONDS)
    except DocumentError:
        return 0
    if proc.returncode != 0:
        return 0
    return parse_osd(proc.stdout.decode('utf-8', errors='replace'))


def parse_osd(report: str) -> int:
    fields = {}
    for line in report.splitlines():
        name, _, value = line.partition(':')
        fields[name.strip().lower()] = value.strip()
    try:
        rotate = int(fields.get('rotate', '0'))
        confidence = float(fields.get('orientation confidence', '0'))
    except ValueError:
        return 0
    return rotate if rotate in (90, 180, 270) and confidence >= MIN_OSD_CONFIDENCE else 0


class LocalDocumentReader:
    def __init__(self, ocr: OcrRunner = tesseract_ocr,
                 orientation: OrientationDetector = tesseract_orientation):
        self._ocr = ocr
        self._orientation = orientation

    def page_count(self, data: bytes, mime_type: str) -> int:
        if mime_type == 'application/pdf':
            with self._open_pdf(data) as doc:
                return doc.page_count
        self._open_image(data)
        return 1

    def render_page(self, data: bytes, mime_type: str, page: int, rendition: str) -> RenderedPage:
        if rendition not in RENDITION_EDGE:
            raise DocumentError('invalid_rendition', 'rendition must be preview or full')
        image, turned = self._upright_page(data, mime_type, page)
        edge = RENDITION_EDGE[rendition]
        if (rendition == 'full' and mime_type == 'image/jpeg' and not turned
                and max(image.width, image.height) <= edge):
            jpeg = data                                  # already the page, upright: no second copy
        else:
            image.thumbnail((edge,) * 2)
            out = io.BytesIO()
            image.convert('RGB').save(out, 'JPEG', quality=85 if rendition == 'preview' else 92,
                                      optimize=True)
            jpeg = out.getvalue()
        return RenderedPage(page=page, rendition=rendition, width=image.width, height=image.height,
                            sha256=hashlib.sha256(jpeg).hexdigest(), jpeg=jpeg)

    def page_text(self, data: bytes, mime_type: str, page: int) -> PageText:
        warnings: list[str] = []
        if mime_type == 'application/pdf':
            with self._open_pdf(data) as doc:
                self._check_page(page, doc.page_count)
                embedded = doc[page - 1].get_text('text') or ''
            if len(embedded.strip()) >= MIN_EMBEDDED_CHARS:
                return PageText(page=page, text=embedded, source='embedded_pdf_text')
            warnings.append('PDF page has little or no text layer; used local OCR')
        image, turned = self._upright_page(data, mime_type, page)
        if turned:
            warnings.append(f'The page was scanned turned; it was rotated {turned}° clockwise before reading')
        png = io.BytesIO()
        image.convert('L').save(png, 'PNG')
        try:
            text = self._ocr(png.getvalue())
        except DocumentError as exc:
            return PageText(page=page, text='', source='none', warnings=(*warnings, str(exc)))
        if not text.strip():
            warnings.append('OCR found no text on this page')
        warnings.append('OCR text may contain recognition errors')
        return PageText(page=page, text=text, source='local_ocr', warnings=tuple(warnings))

    # -- internals -----------------------------------------------------------------
    def _upright_page(self, data: bytes, mime_type: str, page: int):
        """The page image, turned upright, and how far it was turned (clockwise degrees)."""
        image = self._page_image(data, mime_type, page)
        sample = image.convert('L')
        sample.thumbnail((OSD_EDGE,) * 2)
        png = io.BytesIO()
        sample.save(png, 'PNG')
        try:
            turned = int(self._orientation(png.getvalue()))
        except Exception:  # noqa: BLE001 -- an orientation guess must never block reading the page
            turned = 0
        if turned not in (90, 180, 270):
            return image, 0
        return image.rotate(-turned, expand=True), turned

    def _page_image(self, data: bytes, mime_type: str, page: int):
        if mime_type == 'application/pdf':
            from PIL import Image
            with self._open_pdf(data) as doc:
                self._check_page(page, doc.page_count)
                pix = doc[page - 1].get_pixmap(dpi=200)
                return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        self._check_page(page, 1)
        return self._open_image(data)

    @staticmethod
    def _check_page(page: int, count: int) -> None:
        if not 1 <= page <= count:
            raise DocumentError('page_out_of_range', f'page {page} is outside 1..{count}')

    @staticmethod
    def _open_image(data: bytes):
        from PIL import Image, ImageOps
        try:
            image = Image.open(io.BytesIO(data))      # reads the header only
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise DocumentError('unreadable_document', 'image is too large to decode safely')
            image.load()
        except (Image.DecompressionBombError, OSError, ValueError) as exc:
            raise DocumentError('unreadable_document', 'image could not be decoded safely') from exc
        return ImageOps.exif_transpose(image)

    @staticmethod
    def _open_pdf(data: bytes):
        import fitz
        try:
            doc = fitz.open(stream=data, filetype='pdf')
        except Exception as exc:  # noqa: BLE001 -- any parse failure is one answer
            raise DocumentError('unreadable_document', 'PDF could not be opened') from exc
        if doc.needs_pass:
            doc.close()
            raise DocumentError('unreadable_document', 'PDF is password protected')
        if doc.page_count > MAX_PDF_PAGES:
            doc.close()
            raise DocumentError('unreadable_document', f'PDF has more than {MAX_PDF_PAGES} pages')
        return doc
