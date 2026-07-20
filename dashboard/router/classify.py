"""Agent-name detection (Strategy) via a small, fast Letta agent.

Same shape as voice/cleanup.py's LettaAgentCleanup: history cleared each call so
every detection starts fresh. Any parse failure or exception fails CLOSED (no
agent detected) rather than guessing — a bad classification would misroute a
message to the wrong agent, which is worse than not routing at all.
"""
import re
from abc import ABC, abstractmethod

from . import config


class RouteStrategy(ABC):
    @abstractmethod
    def classify(self, text: str) -> dict:
        """Return {"agent": <name or None>, "remainder": <text after the name>}."""
        ...


_AGENT_RE = re.compile(r"AGENT:\s*(.+)", re.IGNORECASE)
_REMAINDER_RE = re.compile(r"REMAINDER:\s*(.*)", re.IGNORECASE | re.DOTALL)
_LEADING_REMAINDER_JUNK_RE = re.compile(r"^[\s,;:.\-—–]+")


def detect_known_agent(text, known_names):
    """Deterministically detect an exact known agent name in transcript text.

    The router agent is still useful for ambiguous phrasing, but exact known
    names must not depend on an LLM round-trip. This is the hands-free path:
    as soon as speech-to-text contains "Mazda", route to Mazda.
    """
    if not text or not known_names:
        return {"agent": None, "remainder": text}

    best = None
    for name in sorted(known_names, key=len, reverse=True):
        # Letter/digit boundaries, not plain \b, so names like "Mazda Router"
        # work while "amazda" does not.
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match and (best is None or match.start() < best[0].start()):
            best = (match, name)

    if not best:
        return {"agent": None, "remainder": text}

    match, name = best
    remainder = _LEADING_REMAINDER_JUNK_RE.sub("", text[match.end():]).strip()
    return {"agent": name, "remainder": remainder}


def build_router_prompt(text, known_names):
    names = ", ".join(known_names) if known_names else "(none provided)"
    return (
        "You detect whether the user is addressing one of a fixed set of named "
        "agents in a running piece of speech-to-text/typed text, and if so, what "
        "they said to that agent.\n"
        "Rules:\n"
        f"1. Known agents: {names}.\n"
        "2. The user may say the agent's name anywhere: before, after, or in the "
        "middle of their request. Everything before the name is unrelated "
        "background noise - ignore it.\n"
        "3. If no known agent is clearly being addressed, reply exactly:\n"
        "   AGENT: NONE\n"
        "   REMAINDER:\n"
        "4. If an agent IS being addressed, reply with exactly two lines:\n"
        "   AGENT: <the matching known agent name, exactly as given above>\n"
        "   REMAINDER: <everything the user said to that agent, excluding the "
        "name itself and anything before it>\n"
        "5. Do NOT answer the request, add commentary, or invent text. Return "
        "ONLY those two lines.\n\n"
        f'Text: "{text}"'
    )


def extract_assistant_text(response):
    """Pull the assistant's reply text out of a Letta /messages response."""
    messages = response.get("messages", []) if isinstance(response, dict) else []
    for msg in messages:
        if msg.get("message_type") != "assistant_message":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict)]
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def parse_router_reply(reply, known_names, original_text):
    """Parse the AGENT:/REMAINDER: reply. Fails closed on anything unexpected."""
    fail_closed = {"agent": None, "remainder": original_text}
    if not reply:
        return fail_closed

    agent_match = _AGENT_RE.search(reply)
    if not agent_match:
        return fail_closed

    agent = agent_match.group(1).strip()
    if not agent or agent.upper() == "NONE":
        return fail_closed

    # Only trust an exact (case-insensitive) match against the known roster -
    # never let the model invent or fuzzy-match a name we don't recognize.
    matched = next((n for n in known_names if n.lower() == agent.lower()), None)
    if not matched:
        return fail_closed

    remainder_match = _REMAINDER_RE.search(reply)
    remainder = remainder_match.group(1).strip() if remainder_match else ""
    return {"agent": matched, "remainder": remainder}


class LettaAgentRouteStrategy(RouteStrategy):
    def __init__(self, client, agent_id, known_names=None, clear_history=True):
        self.client = client
        self.agent_id = agent_id
        self.known_names = known_names or []
        self.clear_history = clear_history

    def classify(self, text: str) -> dict:
        if not text or not text.strip():
            return {"agent": None, "remainder": text}

        exact = detect_known_agent(text, self.known_names)
        if exact.get("agent"):
            return exact

        if not self.agent_id:
            return {"agent": None, "remainder": text}
        try:
            if self.clear_history:
                self.client.clear_messages(self.agent_id)
            prompt = build_router_prompt(text, self.known_names)
            response = self.client.send_message(self.agent_id, prompt)
            reply = extract_assistant_text(response)
            return parse_router_reply(reply, self.known_names, text)
        except Exception:
            return {"agent": None, "remainder": text}  # fail closed


def build_router_strategy() -> RouteStrategy:
    from voice.letta_client import LettaClient

    client = LettaClient(config.LETTA_BASE_URL)
    agent_id = config.ROUTER_AGENT_ID or client.resolve_agent_id(config.ROUTER_AGENT_NAME)
    return LettaAgentRouteStrategy(client, agent_id, known_names=config.ROUTER_AGENT_NAMES)
