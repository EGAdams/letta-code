"""adw_prompts — the Yes/No questions agent_blocks ADWs ask at the dashboard.

The dashboard only records answers; the ADW that asked reads them back. So
what matters here is the state machine (pending -> yes/no/withdrawn/expired,
answered once) and that the poll always shows the oldest open question.
"""
import io
import json

import pytest

import adw_prompts
from http_app import get_routes, post_routes
from http_app.transport import HttpTransportMixin


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    path = tmp_path / 'adw_prompts.json'
    monkeypatch.setattr(adw_prompts, 'PROMPTS_FILE', str(path))
    clock = {'now': 1000.0}
    monkeypatch.setattr(adw_prompts, '_now', lambda: clock['now'])
    return clock


def _ask(question='Run WSL Compact?', **extra):
    result = adw_prompts.create_prompt(
        {'question': question, 'source': 'adw_interface_pc_doctor', **extra})
    assert result['ok']
    return result['prompt']


def test_an_open_question_is_what_the_dashboard_sees():
    asked = _ask(detail='C: has 3.2 GB free')
    polled = adw_prompts.read_prompt()
    assert polled['active'] is True
    assert polled['prompt']['id'] == asked['id']
    assert polled['prompt']['question'] == 'Run WSL Compact?'
    assert polled['prompt']['detail'] == 'C: has 3.2 GB free'


def test_nothing_open_means_no_modal():
    assert adw_prompts.read_prompt() == {'ok': True, 'active': False, 'prompt': None}


def test_the_oldest_open_question_is_shown_first(store):
    first = _ask('First?')
    store['now'] += 1
    _ask('Second?')
    assert adw_prompts.read_prompt()['prompt']['id'] == first['id']


@pytest.mark.parametrize('answer', ['yes', 'no', 'YES', ' No '])
def test_an_answer_is_recorded_for_the_asking_adw(answer):
    asked = _ask()
    result = adw_prompts.answer_prompt({'id': asked['id'], 'answer': answer})
    assert result['ok']
    read_back = adw_prompts.read_prompt(asked['id'])['prompt']
    assert read_back['status'] == answer.strip().lower()
    assert adw_prompts.read_prompt()['active'] is False


def test_a_question_is_answered_once():
    asked = _ask()
    adw_prompts.answer_prompt({'id': asked['id'], 'answer': 'no'})
    second = adw_prompts.answer_prompt({'id': asked['id'], 'answer': 'yes'})
    assert not second['ok']
    assert adw_prompts.read_prompt(asked['id'])['prompt']['status'] == 'no'


def test_only_yes_or_no_is_an_answer():
    asked = _ask()
    assert not adw_prompts.answer_prompt({'id': asked['id'], 'answer': 'maybe'})['ok']
    assert adw_prompts.read_prompt(asked['id'])['prompt']['status'] == 'pending'


def test_an_unanswered_question_expires(store):
    asked = _ask(expires_in_seconds=60)
    store['now'] += 61
    assert adw_prompts.read_prompt()['active'] is False
    assert adw_prompts.read_prompt(asked['id'])['prompt']['status'] == 'expired'
    assert not adw_prompts.answer_prompt({'id': asked['id'], 'answer': 'yes'})['ok']


def test_the_asking_adw_can_withdraw():
    asked = _ask()
    assert adw_prompts.withdraw_prompt({'id': asked['id']})['ok']
    assert adw_prompts.read_prompt(asked['id'])['prompt']['status'] == 'withdrawn'


@pytest.mark.parametrize('body', [{}, {'question': 'Q?'}, {'source': 'x'},
                                  {'question': ' ', 'source': 'x'}, None])
def test_a_question_needs_text_and_a_source(body):
    assert not adw_prompts.create_prompt(body)['ok']


def test_an_unknown_id_is_not_found():
    assert not adw_prompts.read_prompt('nope')['ok']
    assert not adw_prompts.answer_prompt({'id': 'nope', 'answer': 'yes'})['ok']


def test_a_missing_or_corrupt_file_reads_as_empty(tmp_path, monkeypatch):
    bad = tmp_path / 'bad.json'
    bad.write_text('{not json')
    monkeypatch.setattr(adw_prompts, 'PROMPTS_FILE', str(bad))
    assert adw_prompts.read_prompt()['active'] is False
    _ask()
    assert json.loads(bad.read_text())[0]['status'] == 'pending'


# -- through the routes -------------------------------------------------------

class _Handler(get_routes.GetRoutesMixin, post_routes.PostRoutesMixin,
               HttpTransportMixin):
    def __init__(self, path, body=b''):
        self.path = path
        self.status = None
        self.headers = {'Content-Length': str(len(body))}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.sent = {}

    def send_response(self, code):
        self.status = code

    def send_header(self, name, value):
        self.sent[name] = value

    def end_headers(self):
        pass

    def send_error(self, code, *_):
        self.status = code

    def json(self):
        return json.loads(self.wfile.getvalue())


def _route(method, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b''
    h = _Handler(path, body)
    getattr(h, f'do_{method}')()
    return h


def test_the_whole_round_trip_over_http():
    created = _route('POST', '/api/adw-prompt',
                     {'question': 'Run WSL Compact?', 'source': 'pc_doctor'})
    assert created.status == 200
    prompt_id = created.json()['prompt']['id']

    polled = _route('GET', '/api/adw-prompt')
    assert polled.json()['active'] is True

    answered = _route('POST', '/api/adw-prompt-answer', {'id': prompt_id, 'answer': 'yes'})
    assert answered.status == 200

    read_back = _route('GET', f'/api/adw-prompt?id={prompt_id}')
    assert read_back.json()['prompt']['status'] == 'yes'


def test_a_refused_request_is_a_400():
    assert _route('POST', '/api/adw-prompt', {}).status == 400
    assert _route('POST', '/api/adw-prompt-answer', {'id': 'x', 'answer': 'yes'}).status == 400
