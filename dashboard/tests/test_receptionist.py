from voice.receptionist import LettaReceptionistIntentStrategy, build_receptionist_prompt, parse_receptionist_reply


def test_prompt_preserves_transcript_and_requires_json():
    prompt = build_receptionist_prompt("Hey Toyota, let me talk to Mazda.")
    assert "Hey Toyota, let me talk to Mazda." in prompt
    assert "exactly these keys" in prompt


def test_parser_accepts_addressed_cleaned_request():
    assert parse_receptionist_reply('{"addressed": true, "cleaned_text": "Let me talk to Mazda."}') == {"addressed": True, "cleaned_text": "Let me talk to Mazda."}


def test_parser_rejects_invented_or_malformed_output():
    assert parse_receptionist_reply("Toyota can help with that.") == {"addressed": False, "cleaned_text": ""}
    assert parse_receptionist_reply('{"addressed": false, "cleaned_text": "invented request"}') == {"addressed": False, "cleaned_text": ""}


class FakeClient:
    def __init__(self, response=None, fail=False):
        self.response, self.fail = response, fail
        self.cleared, self.sent = [], []

    def clear_messages(self, agent_id): self.cleared.append(agent_id)
    def send_message(self, agent_id, prompt):
        self.sent.append((agent_id, prompt))
        if self.fail: raise RuntimeError("unavailable")
        return self.response


def test_strategy_fails_closed_on_transport_error():
    client = FakeClient(fail=True)
    assert LettaReceptionistIntentStrategy(client, "cleanup-agent").evaluate("Toyota, help") == {"addressed": False, "cleaned_text": ""}
    assert client.cleared == ["cleanup-agent"]


def test_strategy_returns_cleaned_addressed_request():
    client = FakeClient(response={"messages": [{"message_type": "assistant_message", "content": '{"addressed": true, "cleaned_text": "What is on the agenda?"}'}]})
    assert LettaReceptionistIntentStrategy(client, "cleanup-agent").evaluate("Hey Toyota what is on the agenda") == {"addressed": True, "cleaned_text": "What is on the agenda?"}
