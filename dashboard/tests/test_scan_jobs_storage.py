"""The artifact store and the document reader: only by hash, only what it says it is."""

import hashlib
import io
import os
import time

import pytest

from scan_jobs.artifact_store import ArtifactError, FileArtifactStore
from scan_jobs.document_reader import DocumentError, LocalDocumentReader, parse_osd
from scan_jobs.models import RenderedPage
from scan_jobs.rendition_cache import RenditionCache
from tests.scan_jobs_fakes import jpeg, pdf, png


def _put(store, path, data):
    path.write_bytes(data)
    return store.put_file(str(path), not_before_ns=time.time_ns() - 10**10)


def test_a_capture_is_an_immutable_copy(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    src = tmp_path / 'window_scan.jpg'
    first = jpeg((1, 1, 1))
    sha, mime, size = _put(store, src, first)
    src.write_bytes(jpeg((250, 250, 250)))                 # the next scan overwrites the source
    assert (sha, mime, size) == (hashlib.sha256(first).hexdigest(), 'image/jpeg', len(first))
    assert store.read(sha) == first
    assert oct(os.stat(tmp_path / 'store').st_mode & 0o777) == '0o700'


@pytest.mark.parametrize('data, code', [(b'', 'empty_output'), (b'GIF89a....', 'unsupported_type'),
                                        (b'<html>not a scan</html>', 'unsupported_type')])
def test_only_jpeg_png_and_pdf_are_captured(tmp_path, data, code):
    store = FileArtifactStore(tmp_path / 'store')
    with pytest.raises(ArtifactError) as err:
        _put(store, tmp_path / 'out', data)
    assert err.value.code == code


def test_a_symlinked_output_is_refused(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    real = tmp_path / 'secret.jpg'
    real.write_bytes(jpeg((3, 3, 3)))
    link = tmp_path / 'window_scan.jpg'
    link.symlink_to(real)
    with pytest.raises(ArtifactError) as err:
        store.put_file(str(link), not_before_ns=0)
    assert err.value.code == 'capture_failed'


def test_an_output_older_than_the_scan_is_refused(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    src = tmp_path / 'window_scan.jpg'
    src.write_bytes(jpeg((4, 4, 4)))
    with pytest.raises(ArtifactError) as err:
        store.put_file(str(src), not_before_ns=time.time_ns() + 10**10)
    assert err.value.code == 'stale_output'


@pytest.mark.parametrize('bad', ['', '../../etc/passwd', 'a' * 63, 'A' * 64, 'g' * 64])
def test_reads_take_only_a_well_formed_hash(tmp_path, bad):
    store = FileArtifactStore(tmp_path / 'store')
    with pytest.raises(ArtifactError) as err:
        store.read(bad)
    assert err.value.code == 'invalid_artifact'


def test_a_tampered_blob_fails_its_integrity_check(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    sha, _, _ = _put(store, tmp_path / 'out', jpeg((5, 5, 5)))
    blob = next((tmp_path / 'store' / 'blobs').rglob(f'{sha}.*'))
    blob.write_bytes(jpeg((6, 6, 6)))
    with pytest.raises(ArtifactError) as err:
        store.read(sha)
    assert err.value.code == 'artifact_corrupt'


def test_a_blob_swapped_for_a_symlink_is_refused(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    data = jpeg((8, 8, 8))
    sha, _, _ = _put(store, tmp_path / 'out', data)
    blob = next((tmp_path / 'store' / 'blobs').rglob(f'{sha}.*'))
    outside = tmp_path / 'outside.jpg'
    outside.write_bytes(data)
    blob.unlink()
    blob.symlink_to(outside)
    with pytest.raises(ArtifactError) as err:
        store.read(sha)
    assert err.value.code == 'artifact_corrupt'


@pytest.mark.parametrize('name', ['../x', 'a/b', '', 'UPPER.json', '..'])
def test_derived_names_cannot_escape(tmp_path, name):
    store = FileArtifactStore(tmp_path / 'store')
    with pytest.raises(ArtifactError):
        store.put_derived('0' * 64, name, b'x')


def test_a_jpeg_renders_and_reads_as_one_page():
    reader = LocalDocumentReader(ocr=lambda _: 'TOTAL DUE 12.34', orientation=lambda _: 0)
    data = jpeg((255, 255, 255), size=(2550, 3300))
    assert reader.page_count(data, 'image/jpeg') == 1
    preview = reader.render_page(data, 'image/jpeg', 1, 'preview')
    full = reader.render_page(data, 'image/jpeg', 1, 'full')
    assert max(preview.width, preview.height) == 1600 and preview.jpeg.startswith(b'\xff\xd8')
    assert max(full.width, full.height) == 3300
    text = reader.page_text(data, 'image/jpeg', 1)
    assert (text.source, text.text) == ('local_ocr', 'TOTAL DUE 12.34')


def test_a_png_is_read_too():
    reader = LocalDocumentReader(ocr=lambda _: 'x', orientation=lambda _: 0)
    assert reader.render_page(png((0, 128, 0)), 'image/png', 1, 'preview').width == 200


def test_a_multipage_pdf_uses_its_text_layer_per_page():
    reader = LocalDocumentReader(ocr=lambda _: pytest.fail('a PDF with text must not be OCRed'),
                                 orientation=lambda _: 0)
    data = pdf(['Consumers Energy statement page one', 'Second page: amount due 88.10'])
    assert reader.page_count(data, 'application/pdf') == 2
    two = reader.page_text(data, 'application/pdf', 2)
    assert two.source == 'embedded_pdf_text' and 'amount due 88.10' in two.text
    assert reader.render_page(data, 'application/pdf', 2, 'preview').jpeg.startswith(b'\xff\xd8')


@pytest.mark.parametrize('page', [0, 3, 999])
def test_pages_outside_the_document_are_refused(page):
    reader = LocalDocumentReader(ocr=lambda _: 'x', orientation=lambda _: 0)
    with pytest.raises(DocumentError) as err:
        reader.render_page(pdf(['a', 'b']), 'application/pdf', page, 'preview')
    assert err.value.code == 'page_out_of_range'


def test_garbage_claiming_to_be_a_jpeg_is_unreadable():
    with pytest.raises(DocumentError) as err:
        LocalDocumentReader().page_count(b'\xff\xd8\xff' + b'\x00' * 50, 'image/jpeg')
    assert err.value.code == 'unreadable_document'


def test_a_rendition_survives_the_json_cache():
    page = LocalDocumentReader(orientation=lambda _: 0).render_page(jpeg((9, 9, 9)), 'image/jpeg', 1, 'preview')
    assert RenderedPage.model_validate_json(page.model_dump_json()) == page


def test_a_full_jpeg_page_that_needs_nothing_is_the_original():
    data = jpeg((200, 200, 200), size=(2550, 3300))
    full = LocalDocumentReader(orientation=lambda _: 0).render_page(data, 'image/jpeg', 1, 'full')
    assert full.jpeg == data and (full.width, full.height) == (2550, 3300)


def test_a_page_scanned_upside_down_is_turned_before_rendering_and_reading():
    from PIL import Image
    buf = io.BytesIO()
    page = Image.new('RGB', (300, 400), (255, 255, 255))
    page.paste((0, 0, 0), (0, 0, 300, 40))                    # a dark band at the top
    page.rotate(180).save(buf, 'JPEG')                          # ...scanned upside down
    seen = []
    reader = LocalDocumentReader(ocr=lambda png: seen.append(png) or 'READ', orientation=lambda _: 180)
    full = reader.render_page(buf.getvalue(), 'image/jpeg', 1, 'full')
    upright = Image.open(io.BytesIO(full.jpeg)).convert('L')
    assert upright.getpixel((150, 10)) < 60 and upright.getpixel((150, 390)) > 200
    text = reader.page_text(buf.getvalue(), 'image/jpeg', 1)
    assert text.text == 'READ' and any('rotated 180' in w for w in text.warnings)
    assert Image.open(io.BytesIO(seen[0])).convert('L').getpixel((150, 10)) < 60


def test_a_quarter_turn_swaps_the_page_edges():
    reader = LocalDocumentReader(orientation=lambda _: 90)
    full = reader.render_page(jpeg((250, 250, 250), size=(300, 400)), 'image/jpeg', 1, 'full')
    assert (full.width, full.height) == (400, 300)


def test_an_orientation_failure_never_blocks_reading():
    def broken(_):
        raise RuntimeError('osd crashed')
    reader = LocalDocumentReader(ocr=lambda _: 'ok', orientation=broken)
    assert reader.page_text(jpeg((250, 250, 250)), 'image/jpeg', 1).text == 'ok'


@pytest.mark.parametrize('report, turn', [
    ('Page number: 0\nOrientation in degrees: 180\nRotate: 180\nOrientation confidence: 14.76\n', 180),
    ('Rotate: 90\nOrientation confidence: 6.1\n', 90),
    ('Rotate: 180\nOrientation confidence: 0.4\n', 0),       # a guess
    ('Rotate: 45\nOrientation confidence: 9\n', 0),
    ('Too few characters. Skipping this page\n', 0),
    ('Rotate: x\nOrientation confidence: 9\n', 0),
])
def test_only_a_confident_quarter_turn_counts(report, turn):
    assert parse_osd(report) == turn


def test_renditions_are_cached_as_plain_jpegs(tmp_path):
    store = FileArtifactStore(tmp_path / 'store')
    data = jpeg((1, 2, 3), size=(2550, 3300))
    sha, _, _ = _put(store, tmp_path / 'window_scan.jpg', data)
    reader = LocalDocumentReader(orientation=lambda _: 0)
    cache = RenditionCache(store)
    preview = reader.render_page(data, 'image/jpeg', 1, 'preview')
    full = reader.render_page(data, 'image/jpeg', 1, 'full')
    cache.put(sha, preview, data)
    cache.put(sha, full, data)
    derived = tmp_path / 'store' / 'derived' / sha[:2] / sha
    assert (derived / 'page1_preview.jpg').read_bytes() == preview.jpeg
    assert not (derived / 'page1_full.jpg').exists()            # the original is not stored twice
    assert cache.get(sha, 1, 'preview', data) == preview
    assert cache.get(sha, 1, 'full', data) == full
    assert cache.get(sha, 2, 'preview', data) is None
    (derived / 'page1_preview.jpg').write_bytes(b'\xff\xd8\xffhalf')
    assert cache.get(sha, 1, 'preview', data) is None            # a damaged cache renders again
