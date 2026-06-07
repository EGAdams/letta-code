"""TDD: LettaAgentCleanup (Strategy) — Friday -> Frita, with raw fallback.

A fake Letta client stands in for the network so we assert behaviour, not HTTP.
"""
from voice.cleanup import (
    LettaAgentCleanup,
    build_cleanup_prompt,
    extract_assistant_text,
)


class FakeClient:
    def __init__(self, response=None, raise_on_send=False):
        self.response = response or {}
        self.raise_on_send = raise_on_send
        self.cleared = []
        self.sent = []

    def clear_messages(self, agent_id):
        self.cleared.append(agent_id)

    def send_message(self, agent_id, text):
        self.sent.append((agent_id, text))
        if self.raise_on_send:
            raise RuntimeError("boom")
        return self.response


def test_prompt_includes_known_names_and_transcript():
    prompt = build_cleanup_prompt("Tell Friday about this.", ["Scissari", "Frita"])
    assert "Frita" in prompt
    assert "Tell Friday about this." in prompt


def test_extract_assistant_text_skips_reasoning():
    resp = {"messages": [
        {"message_type": "reasoning_message", "reasoning": "thinking..."},
        {"message_type": "assistant_message", "content": "Tell Frita about this."},
    ]}
    assert extract_assistant_text(resp) == "Tell Frita about this."


def test_extract_assistant_text_handles_list_content():
    resp = {"messages": [
        {"message_type": "assistant_message",
         "content": [{"type": "text", "text": "Tell Frita about this."}]},
    ]}
    assert extract_assistant_text(resp) == "Tell Frita about this."


def test_clean_corrects_friday_to_frita_and_clears_history():
    client = FakeClient(response={"messages": [
        {"message_type": "assistant_message", "content": "Tell Frita about this."},
    ]})
    cleanup = LettaAgentCleanup(client, "agent-cleanup", known_names=["Frita"])
    out = cleanup.clean("Tell Friday about this.")

    assert out == "Tell Frita about this."
    assert client.cleared == ["agent-cleanup"]   # Q3: history cleared each call
    assert client.sent and client.sent[0][0] == "agent-cleanup"


def test_clean_falls_back_to_raw_on_send_error():
    client = FakeClient(raise_on_send=True)
    cleanup = LettaAgentCleanup(client, "agent-cleanup")
    assert cleanup.clean("raw text") == "raw text"


def test_clean_falls_back_to_raw_when_no_assistant_text():
    client = FakeClient(response={"messages": [
        {"message_type": "reasoning_message", "reasoning": "..."},
    ]})
    cleanup = LettaAgentCleanup(client, "agent-cleanup")
    assert cleanup.clean("keep me") == "keep me"


def test_clean_empty_transcript_is_passthrough_without_network():
    client = FakeClient()
    cleanup = LettaAgentCleanup(client, "agent-cleanup")
    assert cleanup.clean("   ") == "   "
    assert client.sent == []   # no pointless round-trip
