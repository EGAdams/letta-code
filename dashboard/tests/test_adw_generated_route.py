"""GET /adw_generated/ — the ROL Finance -> Reports -> ADW Generated tab.

The pages and their index.html are written by agent_blocks'
adw_interface_category_web_page.py into paths.ADW_GENERATED_DIR; the route
only serves them, contained the same way as the static fallthrough.
"""
import io

import pytest

from http_app import get_routes


class _Handler(get_routes.GetRoutesMixin):
    def __init__(self, path):
        self.path = path
        self.status = None
        self.headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, code):
        self.status = code

    def send_header(self, name, value):
        self.headers[name] = value

    def end_headers(self):
        pass

    def send_error(self, code, *_):
        self.status = code


def _get(path):
    h = _Handler(path)
    h.do_GET()
    return h


@pytest.fixture
def adw_dir(tmp_path, monkeypatch):
    served = tmp_path / 'web_pages'
    served.mkdir()
    (tmp_path / 'secret.env').write_text('DB_PASSWORD=hunter2')
    monkeypatch.setattr(get_routes, 'ADW_GENERATED_DIR', str(served))
    return served


def test_the_bare_prefix_serves_the_index_uncached(adw_dir):
    (adw_dir / 'index.html').write_text('<ol><li>newest</li></ol>')
    h = _get('/adw_generated/')
    assert h.status == 200
    assert h.wfile.getvalue() == b'<ol><li>newest</li></ol>'
    assert h.headers['Cache-Control'] == 'no-store'
    assert h.headers['Content-Type'].startswith('text/html')


def test_a_linked_page_is_served(adw_dir):
    (adw_dir / 'Gifts_October_24_19_38_56.html').write_text('<h1>Gifts</h1>')
    h = _get('/adw_generated/Gifts_October_24_19_38_56.html')
    assert h.status == 200
    assert h.wfile.getvalue() == b'<h1>Gifts</h1>'


def test_no_index_yet_is_a_placeholder_not_a_404(adw_dir):
    h = _get('/adw_generated/index.html')
    assert h.status == 200
    assert b'No ADW-generated reports yet.' in h.wfile.getvalue()


def test_a_missing_page_is_a_404(adw_dir):
    assert _get('/adw_generated/nope.html').status == 404


def test_traversal_out_of_the_directory_is_refused(adw_dir):
    h = _get('/adw_generated/../secret.env')
    assert h.status == 404
    assert b'hunter2' not in h.wfile.getvalue()
