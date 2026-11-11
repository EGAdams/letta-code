"""POST /api/receptionist-alerts/ack accepts every alert source sources() lists, and only those.

The request model once kept its own hand-typed list of source names. A new
source (the ADW supervisor's task cards, 'adw_tasks') was added to sources()
but not to that list, so every "Got it" was refused with a 400 and the card
came back on the next poll, forever. The names now come from sources() alone.
"""
import pytest

import receptionist_alerts
from tests.http_app_harness import DashboardClient, start_server


class FakeSource:
    name = 'Fake Source'

    def __init__(self):
        self.acked = []

    def alerts(self):
        return {'ok': True, 'alerts': []}

    def acknowledge_alerts(self, ids):
        self.acked.append(ids)
        return {'ok': True, 'acknowledged': len(ids or [])}


@pytest.fixture(scope='module')
def live():
    httpd, _thread, port = start_server()
    yield DashboardClient(port)
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def source(monkeypatch):
    fake = FakeSource()
    monkeypatch.setattr(receptionist_alerts, 'sources', lambda: {'brand_new_source': fake})
    return fake


def test_a_newly_added_source_can_be_acknowledged(live, source):
    r = live.post('/api/receptionist-alerts/ack', {'agent': 'brand_new_source', 'ids': ['card-1']})
    assert r.status == 200, r.text
    assert r.json == {'ok': True, 'acknowledged': 1}
    assert source.acked == [['card-1']]


def test_a_name_sources_does_not_list_is_rejected(live, source):
    r = live.post('/api/receptionist-alerts/ack', {'agent': 'toyota', 'ids': ['card-1']})
    assert r.status == 400
    assert 'no alert source' in r.text
    assert source.acked == []


@pytest.mark.parametrize('body', [{'agent': '', 'ids': ['x']}, {'ids': ['x']},
                                  {'agent': 'brand_new_source', 'ids': ['x'], 'extra': 1}])
def test_malformed_bodies_are_still_rejected(live, source, body):
    assert live.post('/api/receptionist-alerts/ack', body).status == 400
    assert source.acked == []
