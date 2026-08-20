"""A dispatch that never landed must never be reported as accepted.

Regression for 2026-08-19. The Window Scanner intake's POST was rejected with
HTTP 429 -- nothing was queued -- but the acceptance probe counted the
conversation's `in_context_message_ids`, saw the system prompt Letta creates
every conversation with, and reported the dispatch accepted. The scan was
recorded `processing`, the transport-failure path never ran, and it hung until
the Trainer reported it as an infrastructure problem: "the conversation exists
but received nothing after its system prompt".

The live conversation is reproduced below exactly as the Letta server returned
it: one message, `message_type: 'system_message'`.
"""

import pytest

from intake.dispatch_evidence import (
    ConversationMessage,
    DispatchEvidence,
)

# GET /v1/conversations/conv-8f235c63-.../messages on the stalled intake.
NOTHING_WAS_DELIVERED = [
    {
        'id': 'message-33598d6a-2373-4205-a7ed-2ca9f71e080b',
        'role': None,
        'message_type': 'system_message',
        'content': 'You are Letta Code, a persistent coding agent...',
    },
]

DISPATCH_DELIVERED = NOTHING_WAS_DELIVERED + [
    {
        'id': 'message-aaaa',
        'role': 'user',
        'message_type': 'user_message',
        'content': 'A document was scanned on Window Scanner...',
    },
]


# ── the defect ─────────────────────────────────────────────────────────────

def test_a_conversation_holding_only_its_system_prompt_is_not_evidence():
    """The whole bug in one assertion."""
    assert DispatchEvidence.from_payload(NOTHING_WAS_DELIVERED).dispatch_landed is False


def test_the_case_the_probe_was_written_for_still_works():
    """Letta holds the POST open while the agent works, so our HTTP timeout can
    fire on a dispatch that was accepted. That must still read as accepted."""
    assert DispatchEvidence.from_payload(DISPATCH_DELIVERED).dispatch_landed is True


def test_mazdas_own_reply_counts_too():
    """If she has already started answering, the dispatch plainly landed."""
    payload = NOTHING_WAS_DELIVERED + [
        {'role': 'assistant', 'message_type': 'reasoning_message'}]
    assert DispatchEvidence.from_payload(payload).dispatch_landed is True


# ── reading Letta's response ───────────────────────────────────────────────

def test_accepts_the_wrapped_shape_too():
    """Which of the two shapes arrives has changed across Letta versions, and
    neither means anything different."""
    assert DispatchEvidence.from_payload(
        {'messages': DISPATCH_DELIVERED}).dispatch_landed is True
    assert DispatchEvidence.from_payload(
        {'messages': NOTHING_WAS_DELIVERED}).dispatch_landed is False


@pytest.mark.parametrize('payload', [
    None,            # letta_get returns None on any error
    {},
    [],
    'nope',
    b'nope',
    {'messages': None},
    {'messages': 'nope'},
    17,
])
def test_anything_unreadable_counts_as_no_evidence(payload):
    """A scan visibly reported as failed can be run again. One silently
    recorded as in-flight cannot, so an unreadable answer must never be
    optimistic."""
    assert DispatchEvidence.from_payload(payload).dispatch_landed is False


def test_junk_rows_do_not_count_as_a_delivered_message():
    """A row that isn't a mapping tells us nothing -- it must not be mistaken
    for a non-system message and thereby for evidence."""
    assert DispatchEvidence.from_payload([None, 7, 'x']).dispatch_landed is False


def test_only_the_two_fields_that_decide_it_are_bound():
    """Letta's message payload is large and versioned on its own schedule.
    Binding more of it would make an upstream rename look like a failed
    dispatch."""
    message = ConversationMessage.from_row(
        {'message_type': 'user_message', 'role': 'user',
         'some_new_upstream_field': {'deeply': ['nested']}})
    assert message.is_system_prompt is False


def test_a_system_message_is_recognized_by_either_field():
    assert ConversationMessage.from_row(
        {'message_type': 'system_message'}).is_system_prompt is True
    assert ConversationMessage.from_row({'role': 'system'}).is_system_prompt is True


# ── the probe in server.py uses it ─────────────────────────────────────────

def test_probe_reports_not_accepted_for_the_live_stalled_conversation(monkeypatch):
    import server
    monkeypatch.setattr(server, 'letta_get',
                        lambda path, timeout=6: NOTHING_WAS_DELIVERED)
    assert server._mazda_dispatch_was_accepted('conv-8f235c63') is False


def test_probe_reports_accepted_once_the_message_is_there(monkeypatch):
    import server
    monkeypatch.setattr(server, 'letta_get',
                        lambda path, timeout=6: DISPATCH_DELIVERED)
    assert server._mazda_dispatch_was_accepted('conv-8f235c63') is True


def test_probe_asks_for_the_messages_not_the_conversation(monkeypatch):
    """Reading the conversation object is what made the old check wrong: its
    in_context_message_ids cannot tell a system prompt from a dispatch."""
    import server
    asked = []
    monkeypatch.setattr(server, 'letta_get',
                        lambda path, timeout=6: asked.append(path) or [])
    server._mazda_dispatch_was_accepted('conv-8f235c63')
    assert asked and asked[0].endswith('/messages?limit=5')


def test_probe_refuses_a_blank_conversation_id(monkeypatch):
    import server
    monkeypatch.setattr(server, 'letta_get',
                        lambda path, timeout=6: DISPATCH_DELIVERED)
    assert server._mazda_dispatch_was_accepted('') is False
