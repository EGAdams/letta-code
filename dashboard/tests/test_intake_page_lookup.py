"""The adapter between the supporting-document rules and live intake state.

`CallableIntakePageLookup` is three lines of delegation, which is exactly why
it is worth pinning: when it is wrong nothing raises. A page that should offer
its paper scan silently offers nothing, and the dialog renders one fewer
button -- no error, no log line, just a missing document.

The riskiest part is not the delegation but *when the callables are resolved*.
`server._supporting_document_pages()` builds its resolver once and caches it
for the process lifetime, and a dozen supporting-document tests monkeypatch
`server.get_scanner_intake` long after that cache is warm. Binding eagerly
would leave those tests silently exercising the real filesystem.
"""

import pytest

import server
from finance.supporting_documents import (
    CallableIntakePageLookup,
    IIntakePageLookup,
)


class RecordingIntakeState:
    """In-memory stand-in for the server's three intake lookups."""

    def __init__(self, recent=None, scanners=None, reference='scan.jpg'):
        self.recent = recent if recent is not None else {'mode': 'report'}
        self.scanners = scanners if scanners is not None else {}
        self.reference = reference
        self.recent_calls = 0
        self.scanner_keys = []
        self.reference_args = []

    def recent_report(self):
        self.recent_calls += 1
        return self.recent

    def scanner_intake(self, scanner_key):
        self.scanner_keys.append(scanner_key)
        return self.scanners.get(scanner_key)

    def intake_scan_reference(self, intake):
        self.reference_args.append(intake)
        return self.reference


def lookup_over(state):
    """Wire the adapter to a double the way the composition root wires it."""
    return CallableIntakePageLookup(
        lambda: state.recent_report(),
        lambda key: state.scanner_intake(key),
        lambda intake: state.intake_scan_reference(intake),
    )


@pytest.fixture
def state():
    return RecordingIntakeState(
        recent={'mode': 'intake', 'intake': {'doc_kind': 'statement'}},
        scanners={'window': {'image_path': '/staged/window-001.jpg'}},
        reference='/staged/window-001.jpg',
    )


class TestPortCompliance:
    def test_the_adapter_implements_the_port(self, state):
        assert isinstance(lookup_over(state), IIntakePageLookup)

    def test_the_port_itself_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            IIntakePageLookup()

    def test_a_partial_implementation_is_rejected(self):
        class TwoThirds(IIntakePageLookup):
            def recent_report(self):
                return {}

            def scanner_intake(self, scanner_key):
                return {}

        with pytest.raises(TypeError):
            TwoThirds()


class TestRecentReport:
    def test_returns_the_pointer_the_server_reports(self, state):
        assert lookup_over(state).recent_report() == state.recent

    def test_is_called_with_no_arguments(self, state):
        lookup_over(state).recent_report()
        assert state.recent_calls == 1

    @pytest.mark.parametrize('empty', [None, {}, False, 0, ''])
    def test_an_absent_pointer_becomes_an_empty_mapping(self, state, empty):
        """The port promises a mapping; the server may answer None.

        `resolve_recent_report` returns None when nothing has been processed
        yet, and the rules do `recent.get('mode')` on the result. Normalising
        here is what keeps that from being an AttributeError on a fresh box.
        """
        state.recent = empty
        assert lookup_over(state).recent_report() == {}

    def test_resolves_the_callable_on_every_call(self, state):
        lookup = lookup_over(state)
        assert lookup.recent_report()['mode'] == 'intake'
        state.recent = {'mode': 'report', 'url': '/reports/2026-08/report.html'}
        assert lookup.recent_report()['url'] == '/reports/2026-08/report.html'

    def test_a_failing_lookup_propagates(self, state):
        def boom():
            raise RuntimeError('pointer file unreadable')

        lookup = CallableIntakePageLookup(boom, lambda k: {}, lambda i: '')
        with pytest.raises(RuntimeError, match='pointer file unreadable'):
            lookup.recent_report()


class TestScannerIntake:
    def test_returns_the_intake_for_that_scanner(self, state):
        record = lookup_over(state).scanner_intake('window')
        assert record == {'image_path': '/staged/window-001.jpg'}

    @pytest.mark.parametrize('key', ['window', 'freezer', '', 'Window', 'x y'])
    def test_the_scanner_key_is_passed_through_untouched(self, state, key):
        """No normalisation here: SCANNERS is keyed exactly as configured."""
        lookup_over(state).scanner_intake(key)
        assert state.scanner_keys == [key]

    @pytest.mark.parametrize('empty', [None, {}, False, 0])
    def test_an_unknown_scanner_becomes_an_empty_mapping(self, state, empty):
        state.scanners = {'window': empty}
        assert lookup_over(state).scanner_intake('window') == {}

    def test_a_scanner_that_has_never_scanned_is_empty_not_none(self, state):
        assert lookup_over(state).scanner_intake('freezer') == {}

    def test_resolves_the_callable_on_every_call(self, state):
        lookup = lookup_over(state)
        assert lookup.scanner_intake('freezer') == {}
        state.scanners['freezer'] = {'image_path': '/staged/freezer-9.jpg'}
        assert lookup.scanner_intake('freezer')['image_path'].endswith('-9.jpg')

    def test_a_failing_lookup_propagates(self, state):
        def boom(_key):
            raise OSError('pointer file vanished')

        lookup = CallableIntakePageLookup(lambda: {}, boom, lambda i: '')
        with pytest.raises(OSError, match='pointer file vanished'):
            lookup.scanner_intake('window')


class TestIntakeScanReference:
    def test_returns_the_reference_the_server_resolves(self, state):
        intake = {'image_path': '/staged/window-001.jpg'}
        assert lookup_over(state).intake_scan_reference(intake) == state.reference

    def test_the_intake_record_is_handed_over_unchanged(self, state):
        intake = {'image_path': '/staged/x.jpg', 'doc_kind': 'statement'}
        lookup_over(state).intake_scan_reference(intake)
        assert state.reference_args == [intake]
        assert state.reference_args[0] is intake

    @pytest.mark.parametrize('intake', [None, {}, {'doc_kind': 'receipt'}])
    def test_an_empty_intake_still_reaches_the_resolver(self, state, intake):
        """Unlike the other two, this one is *not* normalised.

        Deciding whether a record names a usable scan is the server's job --
        it checks the file actually resolves on disk. Short-circuiting an
        empty record here would only duplicate that rule, badly.
        """
        state.reference = ''
        assert lookup_over(state).intake_scan_reference(intake) == ''
        assert state.reference_args == [intake]

    def test_the_reference_is_returned_verbatim(self, state):
        state.reference = '  /staged/spaced.jpg  '
        result = lookup_over(state).intake_scan_reference({})
        assert result == '  /staged/spaced.jpg  '

    def test_a_failing_resolver_propagates(self, state):
        def boom(_intake):
            raise ValueError('unreadable staged path')

        lookup = CallableIntakePageLookup(lambda: {}, lambda k: {}, boom)
        with pytest.raises(ValueError, match='unreadable staged path'):
            lookup.intake_scan_reference({})


class TestCompositionRoot:
    def test_the_factory_returns_the_port(self):
        assert isinstance(server.server_intake_page_lookup(), IIntakePageLookup)

    def test_the_factory_wires_the_servers_own_intake_state(self, monkeypatch):
        monkeypatch.setattr(server, 'resolve_recent_report',
                            lambda: {'mode': 'report', 'url': '/r.html'})
        monkeypatch.setattr(server, 'get_scanner_intake',
                            lambda key: {'scanner': key})
        monkeypatch.setattr(server, '_intake_source_document',
                            lambda intake: intake.get('scanner', ''))
        lookup = server.server_intake_page_lookup()
        assert lookup.recent_report()['url'] == '/r.html'
        assert lookup.scanner_intake('freezer') == {'scanner': 'freezer'}
        assert lookup.intake_scan_reference({'scanner': 'w'}) == 'w'

    @pytest.mark.parametrize('name,call', [
        ('resolve_recent_report', lambda lk: lk.recent_report()),
        ('get_scanner_intake', lambda lk: lk.scanner_intake('window')),
    ])
    def test_the_factory_binds_late(self, monkeypatch, name, call):
        """Build first, patch second -- the patch must still be seen.

        This is the regression this extraction could introduce. The old class
        called the module globals by name inside its methods; passing the
        function objects to the adapter instead would freeze them at wiring
        time, and every supporting-document test that patches these after the
        resolver cache is warm would quietly run against the real box.
        """
        lookup = server.server_intake_page_lookup()
        monkeypatch.setattr(server, name, lambda *a: {'mode': 'patched'})
        assert call(lookup) == {'mode': 'patched'}

    def test_intake_scan_reference_binds_late_too(self, monkeypatch):
        lookup = server.server_intake_page_lookup()
        monkeypatch.setattr(server, '_intake_source_document',
                            lambda intake: 'patched.jpg')
        assert lookup.intake_scan_reference({}) == 'patched.jpg'

    def test_each_call_builds_an_independent_lookup(self):
        first, second = (server.server_intake_page_lookup(),
                         server.server_intake_page_lookup())
        assert first is not second

    def test_building_a_lookup_reads_nothing(self, monkeypatch):
        """Construction must be inert: the routes build these eagerly."""
        def refuse(*args, **kwargs):
            raise AssertionError('the factory touched intake state')

        monkeypatch.setattr(server, 'resolve_recent_report', refuse)
        monkeypatch.setattr(server, 'get_scanner_intake', refuse)
        monkeypatch.setattr(server, '_intake_source_document', refuse)
        server.server_intake_page_lookup()

    def test_the_adapter_no_longer_lives_in_server(self):
        assert not hasattr(server, '_ServerIntakePageLookup')
        assert (server.CallableIntakePageLookup.__module__
                == 'finance.supporting_documents')


class TestCachedResolverStillSeesPatches:
    """End-to-end guard: the page resolver is cached, the lookups are not."""

    def test_a_scanner_page_reflects_an_intake_patched_after_the_cache_warms(
            self, monkeypatch, tmp_path):
        scan = tmp_path / 'freezer-001.jpg'
        scan.write_bytes(b'jpeg')
        # Warm the process-lifetime resolver cache before patching anything.
        server._supporting_document_pages()
        monkeypatch.setattr(server, 'get_scanner_intake', lambda key: {
            'image_path': str(scan), 'doc_kind': 'statement',
        })
        monkeypatch.setattr(server, '_resolve_local_supporting_document',
                            lambda ref, kind: str(scan))
        reference = server._report_scanned_statement_reference(
            '/scanner_report.html?scanner=freezer')
        assert reference == str(scan)

    def test_a_receipt_intake_offers_no_statement_scan(self, monkeypatch, tmp_path):
        """The rules still apply through the adapter: a receipt is not a
        statement, so the page supplies nothing even though a scan exists."""
        scan = tmp_path / 'freezer-002.jpg'
        scan.write_bytes(b'jpeg')
        server._supporting_document_pages()
        monkeypatch.setattr(server, 'get_scanner_intake', lambda key: {
            'image_path': str(scan), 'doc_kind': 'receipt',
        })
        assert server._report_scanned_statement_reference(
            '/scanner_report.html?scanner=freezer') == ''
