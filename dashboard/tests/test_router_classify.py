"""TDD: LettaAgentRouteStrategy (Strategy) — detect an addressed agent + the
remainder text, failing CLOSED (no agent) on anything unexpected.

A fake Letta client stands in for the network so we assert behaviour, not HTTP.
"""
from router.classify import (
    LettaAgentRouteStrategy,
    build_router_prompt,
    detect_known_agent,
    parse_router_reply,
)

KNOWN = ["Frita", "Scissari", "Hailey", "Jeri", "Mazda", "Suzuki"]


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


def _reply(text):
    return {"messages": [{"message_type": "assistant_message", "content": text}]}


def test_prompt_includes_known_names_and_text():
    prompt = build_router_prompt("Suzuki, check the undo logic.", KNOWN)
    assert "Suzuki" in prompt
    assert "Suzuki, check the undo logic." in prompt


def test_parse_detects_agent_and_remainder():
    reply = "AGENT: Suzuki\nREMAINDER: check the undo logic for the panel."
    result = parse_router_reply(reply, KNOWN, "orig")
    assert result == {"agent": "Suzuki", "remainder": "check the undo logic for the panel."}


def test_parse_none_fails_closed():
    reply = "AGENT: NONE\nREMAINDER:"
    result = parse_router_reply(reply, KNOWN, "orig text")
    assert result == {"agent": None, "remainder": "orig text"}


def test_parse_unknown_agent_name_fails_closed():
    # The model must never be trusted to invent/fuzzy-match a name we don't know.
    reply = "AGENT: Melissa\nREMAINDER: do something"
    result = parse_router_reply(reply, KNOWN, "orig text")
    assert result == {"agent": None, "remainder": "orig text"}


def test_parse_malformed_reply_fails_closed():
    result = parse_router_reply("I'm not sure what you mean.", KNOWN, "orig text")
    assert result == {"agent": None, "remainder": "orig text"}


def test_parse_empty_reply_fails_closed():
    result = parse_router_reply("", KNOWN, "orig text")
    assert result == {"agent": None, "remainder": "orig text"}


def test_detect_known_agent_routes_noisy_mazda_transcript():
    text = (
        "hello I don't know Monster Mazda hello master hey monster a monster "
        "hey master hey I'm trying to can we talk to Mazda monster"
    )
    result = detect_known_agent(text, KNOWN)
    assert result["agent"] == "Mazda"
    assert result["remainder"].startswith("hello master")


def test_detect_known_agent_prefers_full_multiword_name():
    result = detect_known_agent("please ask Mazda Router to inspect this", KNOWN + ["Mazda Router"])
    assert result == {"agent": "Mazda Router", "remainder": "to inspect this"}


def test_classify_exact_name_routes_without_network():
    client = FakeClient()
    strategy = LettaAgentRouteStrategy(client, "agent-router", known_names=KNOWN)
    out = strategy.classify("can we talk to Mazda")
    assert out == {"agent": "Mazda", "remainder": ""}
    assert client.sent == []
    assert client.cleared == []


def test_classify_uses_agent_for_non_exact_detection_and_clears_history():
    client = FakeClient(response=_reply("AGENT: Mazda\nREMAINDER: rerun the intake for that receipt."))
    strategy = LettaAgentRouteStrategy(client, "agent-router", known_names=KNOWN)
    out = strategy.classify("I was scanning receipts, ask the car agent to rerun the intake for that receipt.")

    assert out == {"agent": "Mazda", "remainder": "rerun the intake for that receipt."}
    assert client.cleared == ["agent-router"]  # history cleared each call
    assert client.sent and client.sent[0][0] == "agent-router"


def test_classify_falls_back_to_no_agent_on_send_error():
    client = FakeClient(raise_on_send=True)
    strategy = LettaAgentRouteStrategy(client, "agent-router", known_names=KNOWN)
    assert strategy.classify("some text") == {"agent": None, "remainder": "some text"}


def test_classify_falls_back_to_no_agent_when_no_assistant_text():
    client = FakeClient(response={"messages": [
        {"message_type": "reasoning_message", "reasoning": "..."},
    ]})
    strategy = LettaAgentRouteStrategy(client, "agent-router", known_names=KNOWN)
    assert strategy.classify("some text") == {"agent": None, "remainder": "some text"}


def test_classify_empty_text_is_passthrough_without_network():
    client = FakeClient()
    strategy = LettaAgentRouteStrategy(client, "agent-router", known_names=KNOWN)
    assert strategy.classify("   ") == {"agent": None, "remainder": "   "}
    assert client.sent == []  # no pointless round-trip


def test_classify_no_resolved_agent_id_fails_closed_without_network():
    client = FakeClient()
    strategy = LettaAgentRouteStrategy(client, None, known_names=KNOWN)
    assert strategy.classify("ask the coding agent to do the thing.") == {
        "agent": None, "remainder": "ask the coding agent to do the thing."
    }
    assert client.sent == []
