"""Static-file serving, and the traversal hole that used to be in it.

`GET /../../../../etc/passwd` returned 200 with the file's contents until the
containment check in static_files.py went in. The dashboard binds 0.0.0.0 and is
reachable over Tailscale, so these are regression tests for a live disclosure
bug, not hypotheticals — every one of them fails against the old
`os.path.join(base, path.lstrip('/'))`.
"""
import os

import pytest

from http_app.static_files import resolve_static_asset


@pytest.fixture
def tree(tmp_path):
    """A served root, a secret next to it, and a secret far above it."""
    root = tmp_path / 'served'
    root.mkdir()
    (root / 'dashboard.html').write_text('<html>ok</html>')
    (root / 'sub').mkdir()
    (root / 'sub' / 'app.js').write_text('console.log(1)')
    (tmp_path / 'secret.env').write_text('DB_PASSWORD=hunter2')
    sibling = tmp_path / 'served-old'
    sibling.mkdir()
    (sibling / 'leak.txt').write_text('sibling secret')
    return tmp_path, root


class TestLegitimateAssetsStillResolve:
    def test_a_file_at_the_root(self, tree):
        _, root = tree
        assert resolve_static_asset('/dashboard.html', [root]) == str(root / 'dashboard.html')

    def test_a_file_in_a_subdirectory(self, tree):
        _, root = tree
        assert resolve_static_asset('/sub/app.js', [root]) == str(root / 'sub' / 'app.js')

    def test_the_first_matching_root_wins(self, tmp_path):
        a, b = tmp_path / 'a', tmp_path / 'b'
        a.mkdir(); b.mkdir()
        (a / 'x.css').write_text('from-a')
        (b / 'x.css').write_text('from-b')
        assert resolve_static_asset('/x.css', [a, b]) == str(a / 'x.css')

    def test_a_later_root_is_used_when_the_first_misses(self, tmp_path):
        a, b = tmp_path / 'a', tmp_path / 'b'
        a.mkdir(); b.mkdir()
        (b / 'only-in-b.css').write_text('x')
        assert resolve_static_asset('/only-in-b.css', [a, b]) == str(b / 'only-in-b.css')

    def test_percent_encoding_is_left_alone_as_before(self, tmp_path):
        """Not decoding is deliberate: it is what makes %2e%2e inert."""
        root = tmp_path / 'r'
        root.mkdir()
        (root / 'a%20b.css').write_text('x')
        assert resolve_static_asset('/a%20b.css', [root]) == str(root / 'a%20b.css')


class TestTraversalIsRefused:
    @pytest.mark.parametrize('attack', [
        '/../secret.env',
        '/../../secret.env',
        '/../../../../../../etc/passwd',
        '/sub/../../secret.env',
        '/./../secret.env',
        '/sub/./../../secret.env',
        '/....//secret.env',
        '//../secret.env',
        '/../served-old/leak.txt',
    ])
    def test_dot_dot_escapes_are_refused(self, tree, attack):
        _, root = tree
        assert resolve_static_asset(attack, [root]) is None

    def test_the_classic_payload_no_longer_reads_etc_passwd(self, tree):
        _, root = tree
        assert resolve_static_asset('/../../../../etc/passwd', [root]) is None

    @pytest.mark.parametrize('attack', [
        '/etc/passwd',
        '//etc/passwd',
        '///etc/passwd',
    ])
    def test_absolute_paths_cannot_escape_via_lstrip(self, tree, attack):
        """lstrip('/') is what makes an absolute path look relative; it must
        still land inside the root or be refused."""
        _, root = tree
        assert resolve_static_asset(attack, [root]) is None

    def test_a_symlink_pointing_out_of_tree_is_refused(self, tree):
        tmp, root = tree
        (root / 'escape.env').symlink_to(tmp / 'secret.env')
        assert resolve_static_asset('/escape.env', [root]) is None

    def test_a_symlinked_directory_out_of_tree_is_refused(self, tree):
        tmp, root = tree
        (root / 'out').symlink_to(tmp / 'served-old')
        assert resolve_static_asset('/out/leak.txt', [root]) is None

    def test_a_symlink_staying_inside_the_root_is_allowed(self, tree):
        _, root = tree
        (root / 'alias.html').symlink_to(root / 'dashboard.html')
        assert resolve_static_asset('/alias.html', [root]) == str(root / 'dashboard.html')

    def test_a_sibling_root_sharing_a_name_prefix_is_not_contained(self, tree):
        """'/srv/dashboard-old' must not count as inside '/srv/dashboard'."""
        tmp, root = tree
        assert resolve_static_asset('/../served-old/leak.txt', [root]) is None


class TestRefusedInputs:
    @pytest.mark.parametrize('bad', ['', '/', '//', '///'])
    def test_empty_paths_resolve_to_nothing(self, tree, bad):
        _, root = tree
        assert resolve_static_asset(bad, [root]) is None

    def test_a_nul_byte_is_refused_rather_than_raising(self, tree):
        _, root = tree
        assert resolve_static_asset('/dashboard.html\x00.png', [root]) is None

    def test_a_directory_is_not_served_as_a_file(self, tree):
        _, root = tree
        assert resolve_static_asset('/sub', [root]) is None

    def test_a_missing_file_resolves_to_nothing(self, tree):
        _, root = tree
        assert resolve_static_asset('/nope.css', [root]) is None

    def test_no_roots_resolves_to_nothing(self):
        assert resolve_static_asset('/dashboard.html', []) is None

    def test_a_nonexistent_root_is_skipped_not_fatal(self, tree):
        _, root = tree
        missing = os.path.join(str(root), 'does-not-exist')
        assert resolve_static_asset('/dashboard.html', [missing, root]) is not None
