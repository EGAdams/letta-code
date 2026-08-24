"""Judging a scan before anything expensive happens to it.

`tests/test_server.py` covers both functions end to end and those tests pass
unchanged. What they never reached is the reason the blank-page gate is built
the way it is: it scores the *busiest tile* of an 8x8 grid rather than the
whole page, because the ordinary scan is a small receipt lying on a full
letter-size flatbed. 95% of that image genuinely is blank paper, which drags a
whole-page stddev down to around 6.4 -- below any threshold that still catches
a truly empty sheet. Whole-page scoring would therefore reject real receipts,
and the only way to see that is to build both kinds of page and compare.

These tests synthesise images rather than reading fixtures, so the geometry
being asserted is visible in the test itself.
"""
import pytest

import server
from hardware import scan_result

Image = pytest.importorskip('PIL.Image')
ImageDraw = pytest.importorskip('PIL.ImageDraw')

LETTER = (850, 1100)  # 100 dpi letter, the shape the flatbeds produce


def blank_page(size=LETTER, shade=255):
    return Image.new('L', size, shade)


#: A till receipt at 100 dpi: about 1.8 x 2.2 inches of pale thermal paper with
#: thin grey text, lying on a letter-size flatbed. Deliberately modest -- a big
#: high-contrast rectangle would pass whole-page scoring too and prove nothing.
SMALL_RECEIPT = (60, 80, 240, 300)


def page_with_receipt(size=LETTER, box=SMALL_RECEIPT, ink=110):
    """A small pale receipt on a large white page: the ordinary real scan."""
    img = blank_page(size)
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill=248)
    x0, y0, x1, y1 = box
    for n, y in enumerate(range(y0 + 12, y1 - 8, 16)):
        right = max(x0 + 12, x1 - 10 - (n % 3) * 30)
        draw.rectangle((x0 + 10, y, right, y + 2), fill=ink)
    return img


def save(img, tmp_path, name='scan.jpg'):
    path = tmp_path / name
    img.save(path)
    return str(path)


class TestBusiestTileSpread:
    """The grid is the whole idea; these pin why."""

    def test_a_blank_page_has_no_busy_tile_anywhere(self):
        assert scan_result._busiest_tile_spread(blank_page()) == pytest.approx(0.0)

    def test_a_small_receipt_makes_at_least_one_tile_busy(self):
        assert scan_result._busiest_tile_spread(page_with_receipt()) > \
            scan_result._BLANK_SCAN_STDDEV

    def test_whole_page_scoring_would_have_rejected_that_same_receipt(self):
        """The measurement that justifies the grid, made explicit."""
        from PIL import ImageStat
        page = page_with_receipt()
        whole_page = ImageStat.Stat(page).stddev[0]
        assert whole_page < scan_result._BLANK_SCAN_STDDEV
        assert scan_result._busiest_tile_spread(page) > scan_result._BLANK_SCAN_STDDEV

    @pytest.mark.parametrize('corner', [
        (10, 10, 190, 230),            # top-left
        (650, 10, 830, 230),           # top-right
        (10, 850, 190, 1070),          # bottom-left
        (650, 850, 830, 1070),         # bottom-right
        (335, 440, 515, 660),          # dead centre
    ])
    def test_it_finds_the_receipt_wherever_it_landed_on_the_glass(self, corner):
        """Operators drop paper anywhere; the gate must not depend on placement."""
        page = page_with_receipt(box=corner)
        assert scan_result._busiest_tile_spread(page) > scan_result._BLANK_SCAN_STDDEV

    def test_a_receipt_straddling_a_tile_boundary_is_still_found(self):
        """An 8x8 grid on 850x1100 seams at x=425 and y=550; a receipt sitting
        across both corners is split over four tiles and must still register.
        """
        page = page_with_receipt(box=(350, 470, 500, 630), ink=40)
        assert scan_result._busiest_tile_spread(page) > scan_result._BLANK_SCAN_STDDEV

    def test_a_uniformly_grey_page_is_as_blank_as_a_white_one(self):
        """A lid left open scans mid-grey, not black; still nothing on it."""
        assert scan_result._busiest_tile_spread(blank_page(shade=128)) == \
            pytest.approx(0.0)

    @pytest.mark.parametrize('size', [
        (1, 1), (2, 2), (3, 3), (7, 7), (8, 8),
        (4, 1100),   # a sliver: narrower than the grid, full height
        (850, 4),    # and the other way round
    ])
    def test_a_page_smaller_than_the_grid_does_not_crash(self, size):
        """Tiles clamp to 1px, so the last few used to start past the edge and
        produce a box whose right edge was left of its left edge -- which
        Pillow rejects. The `max(1, ...)` on the tile size shows the intent was
        already to cope with this; the loop just did not stop at the edge.

        The crash was swallowed by inspect_scan_image_quality's except, so a
        perfectly decodable sliver was reported as "could not be decoded".
        """
        assert scan_result._busiest_tile_spread(blank_page(size)) == pytest.approx(0.0)

    def test_a_tiny_but_readable_image_is_not_called_undecodable(self, tmp_path):
        """The user-visible half of the same bug."""
        img = blank_page((6, 6))
        img.putpixel((0, 0), 0)
        img.putpixel((5, 5), 0)
        path = tmp_path / 'sliver.png'
        img.save(path)
        assert 'could not be decoded' not in \
            scan_result.inspect_scan_image_quality(str(path))['reason']

    def test_the_score_is_the_maximum_not_the_average(self):
        """Averaging tiles reintroduces exactly the dilution the grid removes."""
        page = page_with_receipt()
        busiest = scan_result._busiest_tile_spread(page)
        from PIL import ImageStat
        tiles = []
        w, h = page.size
        tw, th = w // 8, h // 8
        for r in range(8):
            for c in range(8):
                crop = page.crop((c * tw, r * th, (c + 1) * tw, (r + 1) * th))
                tiles.append(ImageStat.Stat(crop).stddev[0])
        assert busiest == pytest.approx(max(tiles), abs=0.5)
        assert sum(tiles) / len(tiles) < busiest


class TestInspectScanImageQuality:
    def test_a_real_receipt_passes(self, tmp_path):
        result = scan_result.inspect_scan_image_quality(
            save(page_with_receipt(), tmp_path))
        assert result == {'ok': True, 'blank_like': False, 'reason': ''}

    def test_a_blank_sheet_is_stopped_at_the_door(self, tmp_path):
        result = scan_result.inspect_scan_image_quality(save(blank_page(), tmp_path))
        assert result['ok'] is False
        assert result['blank_like'] is True
        assert 'blank' in result['reason'].lower()

    def test_a_colour_scan_is_converted_before_judging(self, tmp_path):
        """The flatbeds produce RGB; stddev on a colour image is per-channel."""
        rgb = page_with_receipt().convert('RGB')
        assert scan_result.inspect_scan_image_quality(
            save(rgb, tmp_path, 'colour.png'))['ok'] is True

    @pytest.mark.parametrize('content, name', [
        (b'', 'empty.jpg'),
        (b'\xff\xd8\xff', 'truncated.jpg'),
        (b'<html>WIA error</html>', 'error.jpg'),
        (b'%PDF-1.4 not an image', 'wrong.jpg'),
    ])
    def test_an_undecodable_file_is_rejected_not_waved_through(
            self, tmp_path, content, name):
        """Undecodable here means undecodable for every downstream reader too."""
        path = tmp_path / name
        path.write_bytes(content)
        result = scan_result.inspect_scan_image_quality(str(path))
        assert result['ok'] is False
        assert 'could not be decoded' in result['reason']

    def test_a_missing_file_is_rejected(self, tmp_path):
        assert scan_result.inspect_scan_image_quality(
            str(tmp_path / 'nope.jpg'))['ok'] is False

    def test_no_pillow_means_no_opinion_not_a_rejection(self, monkeypatch, tmp_path):
        """Fails OPEN. A missing optional dependency must never eat real scans."""
        monkeypatch.setattr(scan_result, 'Image', None)
        monkeypatch.setattr(scan_result, 'ImageStat', None)
        result = scan_result.inspect_scan_image_quality(str(tmp_path / 'nope.jpg'))
        assert result['ok'] is True
        assert result['blank_like'] is False
        assert 'pillow unavailable' in result['reason'].lower()

    def test_half_a_pillow_is_still_no_opinion(self, monkeypatch, tmp_path):
        monkeypatch.setattr(scan_result, 'ImageStat', None)
        assert scan_result.inspect_scan_image_quality(
            save(blank_page(), tmp_path))['ok'] is True

    def test_the_file_is_closed_before_returning(self, tmp_path):
        """A leaked handle per scan wedges the box after enough of them."""
        path = save(page_with_receipt(), tmp_path)
        for _ in range(50):
            scan_result.inspect_scan_image_quality(path)
        import os
        os.remove(path)  # would raise on Windows; proves no handle is held


class TestClassifyScanResult:
    """Each outcome tells the operator to do something different."""

    def test_a_clean_exit_with_an_image_is_ready(self):
        assert scan_result.classify_scan_result(0, 'done', True) == {
            'status': 'ready', 'log': 'done'}

    def test_a_clean_exit_with_nothing_on_disk_is_named_distinctly(self):
        """'Scan failed (exit 0)' is true and useless; this becomes a failed intake."""
        result = scan_result.classify_scan_result(0, '', False)
        assert result['status'] == 'error'
        assert result['empty_output'] is True
        assert 'missing or empty' in result['error']

    @pytest.mark.parametrize('log', [
        'SCANNER_BUSY', 'scanner_busy', 'The device is busy',
        'WIA: device busy', 'resource busy', 'ERROR: DEVICE IS BUSY',
    ])
    def test_every_busy_phrasing_the_script_emits(self, log):
        assert scan_result.classify_scan_result(1, log, False)['status'] == 'busy'

    @pytest.mark.parametrize('log', [
        'SCANNER_OFFLINE', 'scanner_offline', 'device not found',
        'NOT FOUND',
    ])
    def test_every_offline_phrasing(self, log):
        result = scan_result.classify_scan_result(1, log, False)
        assert result['status'] == 'offline'
        assert 'powered off' in result['error']

    def test_busy_is_checked_before_offline(self):
        """A log naming both is a busy device, not a missing one: waiting fixes it."""
        result = scan_result.classify_scan_result(
            1, 'SCANNER_BUSY: device not found in free state', False)
        assert result['status'] == 'busy'

    def test_an_unrecognised_failure_surfaces_the_log(self):
        result = scan_result.classify_scan_result(3, 'WIA 0x80210015', False)
        assert result['status'] == 'error'
        assert result['error'] == 'WIA 0x80210015'

    def test_a_silent_failure_names_the_exit_code(self):
        assert scan_result.classify_scan_result(9, '', False)['error'] == \
            'Scan failed (exit 9)'

    def test_a_none_log_does_not_crash_the_lowercasing(self):
        assert scan_result.classify_scan_result(1, None, False)['status'] == 'error'

    def test_an_image_on_disk_cannot_rescue_a_nonzero_exit(self):
        """A partial transfer leaves bytes behind; the exit code is the truth."""
        assert scan_result.classify_scan_result(1, 'SCANNER_BUSY', True)['status'] == 'busy'

    def test_the_log_travels_with_every_outcome(self):
        for args in [(0, 'a', True), (0, 'b', False), (1, 'SCANNER_BUSY', False),
                     (1, 'not found', False), (2, 'other', False)]:
            assert 'log' in scan_result.classify_scan_result(*args)


class TestScanOutputReady:
    def test_a_written_file_is_ready(self, tmp_path):
        path = tmp_path / 'scan.jpg'
        path.write_bytes(b'\xff\xd8\xff')
        assert scan_result._scan_output_ready(str(path)) is True

    def test_a_zero_byte_file_is_not(self, tmp_path):
        """The script creates the output before filling it; polling sees both."""
        path = tmp_path / 'scan.jpg'
        path.write_bytes(b'')
        assert scan_result._scan_output_ready(str(path)) is False

    def test_a_missing_file_is_not(self, tmp_path):
        assert scan_result._scan_output_ready(str(tmp_path / 'nope.jpg')) is False

    def test_a_directory_is_not(self, tmp_path):
        assert scan_result._scan_output_ready(str(tmp_path)) is False

    def test_an_unreadable_path_is_not_an_exception(self):
        assert scan_result._scan_output_ready('/proc/self/mem/nope/deeper') is False


class TestServerReExport:
    def test_the_judgements_no_longer_live_in_server(self):
        for name in ('classify_scan_result', 'inspect_scan_image_quality',
                     '_busiest_tile_spread', '_scan_output_ready'):
            assert getattr(server, name).__module__ == 'hardware.scan_result'

    def test_pillow_left_server_with_the_gate_it_backs(self):
        """Nothing else in server.py ever used it."""
        assert not hasattr(server, 'ImageStat')
