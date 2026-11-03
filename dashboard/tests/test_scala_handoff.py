"""A page the vision check calls non-financial is left to Scala: staged, recorded, no Mazda turn."""

import pytest

from intake import scala_handoff
from intake.document_processing import Collaborators, process_scanned_document
from intake.scala_handoff import LEFT_FOR_SCALA_PREFIX, left_for_scala

TAX = {'ok': True, 'doc_kind': 'unknown', 'vision_doc_type': 'tax_document', 'vision_confidence': 0.95}


@pytest.mark.parametrize('facade, override, expected', [
    (TAX, None, True),
    (dict(TAX, vision_doc_type='other'), None, True),
    (dict(TAX, vision_doc_type='receipt'), None, False),            # a JPEG receipt is also "unknown"
    (dict(TAX, vision_doc_type='invoice'), None, False),
    (dict(TAX, vision_confidence=0.6), None, False),
    (dict(TAX, vision_confidence='n/a'), None, False),
    ({'ok': True, 'doc_kind': 'unknown'}, None, False),            # no vision answer at all
    (dict(TAX, doc_kind='statement'), None, False),
    (dict(TAX, ok=False), None, False),
    (dict(TAX, statement_preflight={'ok': True}), None, False),
    (TAX, 'statement', False),                                       # the operator said statement
])
def test_only_a_confident_non_financial_call_skips_mazda(facade, override, expected):
    assert left_for_scala(facade, override) is expected


def test_the_skip_can_be_turned_off(monkeypatch):
    monkeypatch.setenv('DASHBOARD_SCALA_SKIPS_MAZDA', '0')
    assert left_for_scala(TAX) is False


class _Deps:
    def __init__(self, tmp_path, facade):
        self.image = tmp_path / 'window_scan.jpg'
        self.image.write_bytes(b'\xff\xd8\xff' + b'x' * 64)
        self.facade, self.recorded, self.calls = facade, [], []

    def collaborators(self):
        def note(name, value=None):
            def call(*a, **k):
                self.calls.append(name)
                return value
            return call

        def record(path, name, **kw):
            self.recorded.append((path, kw))

        return Collaborators(
            scanners={'window': {'name': 'Window Scanner', 'output': self.image.name}},
            scan_tools_dir=str(self.image.parent), scan_locked=lambda: False,
            record_recent_intake=record, human_override_facade=note('override'),
            run_intake_facade=lambda *a, **k: self.facade,
            document_vision_health=lambda: {'ok': True},
            inspect_scan_image_quality=lambda _: {'ok': True},
            run_statement_preflight=lambda *a, **k: None,
            build_pipeline_result=lambda facade, mazda_dispatched: {
                'ok': True, 'mazda_dispatched': mazda_dispatched, 'doc_kind': facade.get('doc_kind')},
            scan_content_sha256=lambda _: 'a' * 64, claim_scan_dispatch=lambda *a: True,
            stage_scan_for_mazda=note('stage', '/staged/incoming_scans/scan_1.jpg'),
            write_statement_preflight_payload=note('payload'),
            create_mazda_conversation=note('conversation', 'conv-1'),
            dispatch_mazda_or_block=note('dispatch', True),
            notify_mazda_of_scan_and_record_failure=note('notify'),
            release_scan_dispatch=note('release'), current_execution_mode=lambda: 'auto')


def test_a_tax_form_is_staged_for_scala_and_mazda_never_starts(tmp_path):
    deps = _Deps(tmp_path, TAX)
    result = process_scanned_document(deps.collaborators(), 'window')
    assert deps.calls == ['stage']                                   # no conversation, no dispatch
    assert result['left_for_scala'] is True and result['mazda_dispatched'] is False
    (path, kw), = deps.recorded
    assert path == '/staged/incoming_scans/scan_1.jpg' and kw['status'] == 'complete'
    assert kw['status_detail'].startswith(LEFT_FOR_SCALA_PREFIX) and 'tax_document' in kw['status_detail']


def test_a_receipt_still_goes_to_mazda(tmp_path):
    deps = _Deps(tmp_path, dict(TAX, vision_doc_type='receipt'))
    result = process_scanned_document(deps.collaborators(), 'window')
    assert deps.calls == ['stage', 'conversation', 'dispatch']
    assert result['mazda_dispatched'] is True and 'left_for_scala' not in result


def test_the_prefix_is_what_the_template_starts_with():
    assert scala_handoff.LEFT_FOR_SCALA.startswith(LEFT_FOR_SCALA_PREFIX)
