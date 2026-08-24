"""What came back from the scanner, and whether it is worth going on with.

Two pure judgements, both made before anything expensive happens:

* `classify_scan_result` reads the scan script's exit code and log and decides
  between busy, offline, empty and failed. The distinctions matter because the
  dashboard says different things to the operator for each -- "the scanner is
  busy" is a wait, "not found" is a power cycle.
* `inspect_scan_image_quality` decides whether the page has anything on it. A
  blank capture used to travel the whole pipeline -- classify, parse, an agent
  dispatch, a Trainer verdict -- before anyone noticed the sheet was empty.

Neither talks to a scanner, and the module carries the optional Pillow import
so the rest of the server does not have to know about it.
"""

import os

try:  # Pillow backs the blank-scan gate only. The server must still boot
    # without it -- inspect_scan_image_quality degrades to "let it through".
    from PIL import Image, ImageStat
except Exception:  # pragma: no cover - exercised by monkeypatching both to None
    Image = None
    ImageStat = None


def classify_scan_result(returncode, log, image_exists):
    """Pure classifier for a scan script's outcome → {status, error?, log}.

    Markers emitted by scan_device.ps1: SCANNER_BUSY (also "device is busy"),
    SCANNER_OFFLINE (also "not found"). A clean exit with the image on disk is
    `ready`. Kept pure (no I/O) so it's unit-testable.
    """
    low = (log or '').lower()
    if returncode == 0 and image_exists:
        return {'status': 'ready', 'log': log}
    if returncode == 0:
        # The script believes it succeeded but wrote nothing readable. Flagged
        # distinctly because the log is empty too, so the generic branch below
        # would report "Scan failed (exit 0)" -- true and useless. run_scanner
        # turns this into a visible failed intake.
        return {'status': 'error', 'empty_output': True,
                'error': 'The scanner output is missing or empty.', 'log': log}
    if ('scanner_busy' in low or 'device is busy' in low
            or 'device busy' in low or 'resource busy' in low):
        return {'status': 'busy', 'error': 'The scanner is busy.', 'log': log}
    if 'scanner_offline' in low or 'not found' in low:
        return {'status': 'offline',
                'error': 'Scanner not found (powered off or disconnected).',
                'log': log}
    return {'status': 'error',
            'error': log or f'Scan failed (exit {returncode})', 'log': log}


# Measured over the 311 scans already filed in readable_documents: the flattest
# real one reads 27.8 and a blank sheet reads 0.0, so this sits with a wide
# margin on both sides.
_BLANK_SCAN_STDDEV = 12.0
# Judged per tile, not over the whole page, because the ordinary case is a
# small receipt on a full letter-size flatbed: 95% of that scan IS blank paper,
# which drags a whole-page stddev down to 6.4 -- below any threshold that still
# catches a genuinely empty sheet. A grid coarse enough that a receipt fills
# several tiles, fine enough that one small receipt still fills one.
_BLANK_SCAN_GRID = 8


def _busiest_tile_spread(gray):
    """Greatest grey-level spread found in any one tile of the page.

    A blank sheet has no busy tile anywhere; a page with anything printed on it
    has at least one, wherever on the glass it happened to land.
    """
    width, height = gray.size
    tile_w = max(1, width // _BLANK_SCAN_GRID)
    tile_h = max(1, height // _BLANK_SCAN_GRID)
    busiest = 0.0
    for row in range(_BLANK_SCAN_GRID):
        top = row * tile_h
        # An image narrower or shorter than the grid gets tiles of 1px, and the
        # last few then start past the edge -- `min()` alone leaves a box whose
        # right edge is left of its left edge, which Pillow rejects. Stopping at
        # the edge is what the `max(1, ...)` above was already reaching for.
        if top >= height:
            break
        for col in range(_BLANK_SCAN_GRID):
            left = col * tile_w
            if left >= width:
                break
            box = (left, top,
                   min(width, left + tile_w),
                   min(height, top + tile_h))
            busiest = max(busiest, ImageStat.Stat(gray.crop(box)).stddev[0])
    return busiest


def inspect_scan_image_quality(path):
    """Is this scan worth spending Mazda's turn on? -> {ok, blank_like, reason}.

    A blank capture used to travel the whole pipeline -- classify, parse, an
    agent dispatch, a Trainer verdict -- before anyone noticed there was
    nothing on the page. This is the cheap local check that stops it at the
    door, in keeping with the pipeline's "cheapest reliable tool first" rule.

    Fails OPEN in the one case it cannot judge: no Pillow, no opinion. A
    missing optional dependency must never silently swallow real scans.
    """
    if Image is None or ImageStat is None:
        return {'ok': True, 'blank_like': False,
                'reason': 'Pillow unavailable; scan image quality was not checked.'}
    try:
        with Image.open(path) as img:
            img.load()
            spread = _busiest_tile_spread(img.convert('L'))
    except Exception:
        # Truncated transfer, a WIA error page, a zero-byte JPEG with a header.
        # Undecodable here means undecodable for every downstream reader too.
        return {'ok': False, 'blank_like': True,
                'reason': 'The scan could not be decoded as an image.'}
    if spread < _BLANK_SCAN_STDDEV:
        return {'ok': False, 'blank_like': True,
                'reason': ('The scan appears blank or unreadable '
                           '(nearly uniform page).')}
    return {'ok': True, 'blank_like': False, 'reason': ''}


def _scan_output_ready(path):
    """A scanner result is usable only when it contains actual bytes."""
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False
