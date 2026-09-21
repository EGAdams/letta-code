import pytest

from voice.receptionist import (
    DeterministicReceptionistIntentStrategy,
    LettaReceptionistIntentStrategy,
    build_receptionist_strategy,
    build_receptionist_prompt,
    parse_receptionist_reply,
)


def test_prompt_preserves_transcript_and_requires_json():
    prompt = build_receptionist_prompt("Hey Toyota, let me talk to Mazda.")
    assert "Hey Toyota, let me talk to Mazda." in prompt
    assert "exactly these keys" in prompt


def test_parser_accepts_addressed_cleaned_request():
    assert parse_receptionist_reply(
        '{"addressed": true, "cleaned_text": "Let me talk to Mazda."}'
    ) == {"addressed": True, "cleaned_text": "Let me talk to Mazda."}


def test_parser_rejects_invented_or_malformed_output():
    assert parse_receptionist_reply("Toyota can help with that.") == {
        "addressed": False, "cleaned_text": ""
    }
    assert parse_receptionist_reply(
        '{"addressed": false, "cleaned_text": "invented request"}'
    ) == {"addressed": False, "cleaned_text": ""}


class FakeClient:
    def __init__(self, response=None, fail=False):
        self.response = response
        self.fail = fail
        self.cleared = []
        self.sent = []

    def clear_messages(self, agent_id):
        self.cleared.append(agent_id)

    def send_message(self, agent_id, prompt):
        self.sent.append((agent_id, prompt))
        if self.fail:
            raise RuntimeError("unavailable")
        return self.response


def test_strategy_uses_cleanup_agent_and_fails_closed_on_transport_error():
    client = FakeClient(fail=True)
    strategy = LettaReceptionistIntentStrategy(client, "cleanup-agent")
    assert strategy.evaluate("Toyota, what is on the agenda?") == {
        "addressed": False, "cleaned_text": ""
    }
    assert client.cleared == ["cleanup-agent"]
    assert client.sent


def test_strategy_returns_cleaned_addressed_request():
    client = FakeClient(response={
        "messages": [{
            "message_type": "assistant_message",
            "content": '{"addressed": true, "cleaned_text": "What is on the agenda?"}',
        }]
    })
    strategy = LettaReceptionistIntentStrategy(client, "cleanup-agent")
    assert strategy.evaluate("Hey Toyota what is on the agenda") == {
        "addressed": True, "cleaned_text": "What is on the agenda?"
    }


@pytest.mark.parametrize(
    ("transcript", "expected_text"),
    [
        ("Toyota, what are we working on?", "what are we working on?"),
        ("Hey Toyota what is next", "what is next"),
        ("hello, TOYOTA: please send this", "please send this"),
        ("Okay Toyota - check the agenda", "check the agenda"),
    ],
)
def test_deterministic_strategy_strips_a_clear_toyota_wake_phrase(
    transcript, expected_text
):
    assert DeterministicReceptionistIntentStrategy().evaluate(transcript) == {
        "addressed": True,
        "cleaned_text": expected_text,
    }


@pytest.mark.parametrize(
    "transcript",
    [
        "",
        "Toyota",
        "I was thinking about Toyota yesterday",
        "Tell Mazda what Toyota said",
        "Hey Mazda, what is next?",
    ],
)
def test_deterministic_strategy_fails_closed_without_a_toyota_request(transcript):
    assert DeterministicReceptionistIntentStrategy().evaluate(transcript) == {
        "addressed": False,
        "cleaned_text": "",
    }


def test_factory_defaults_to_deterministic_strategy_without_a_letta_call(monkeypatch):
    from voice import config, letta_client

    monkeypatch.setattr(config, "RECEPTIONIST_INTENT_MODE", "deterministic")
    monkeypatch.setattr(
        letta_client,
        "LettaClient",
        lambda *args: (_ for _ in ()).throw(AssertionError("must stay local")),
    )
    assert isinstance(build_receptionist_strategy(), DeterministicReceptionistIntentStrategy)


def test_factory_rejects_unknown_receptionist_intent_mode(monkeypatch):
    from voice import config

    monkeypatch.setattr(config, "RECEPTIONIST_INTENT_MODE", "typo")
    with pytest.raises(ValueError, match="unsupported receptionist intent mode"):
        build_receptionist_strategy()
