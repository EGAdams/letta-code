"""Toyota receptionist intent policies (Strategy).

The default policy recognizes an explicit Toyota wake phrase locally. The
legacy Letta policy remains opt-in. Both fail closed, and raw speech remains
available to the user.
"""
import json
import re
from abc import ABC, abstractmethod

from . import config
from .cleanup import extract_assistant_text


class ReceptionistIntentStrategy(ABC):
    @abstractmethod
    def evaluate(self, transcript: str) -> dict:
        """Return {addressed: bool, cleaned_text: str}."""
        ...


class DeterministicReceptionistIntentStrategy(ReceptionistIntentStrategy):
    """Recognize an explicit Toyota wake phrase without a model round trip."""

    _WAKE_PHRASE = re.compile(
        r"^\s*(?:(?:hey|hi|hello|ok|okay)\b[\s,.:;!?-]*)?"
        r"toyota\b[\s,.:;!?-]*(?P<request>.+?)\s*$",
        re.IGNORECASE,
    )

    def evaluate(self, transcript: str) -> dict:
        if not isinstance(transcript, str):
            return {"addressed": False, "cleaned_text": ""}
        match = self._WAKE_PHRASE.fullmatch(transcript)
        request = match.group("request").strip() if match else ""
        if not request:
            return {"addressed": False, "cleaned_text": ""}
        return {"addressed": True, "cleaned_text": request}


def build_receptionist_prompt(transcript: str) -> str:
    return (
        "You are a strict receptionist-intent detector for Toyota.\n"
        "Determine whether this raw speech transcript clearly addresses Toyota "
        "as the dashboard receptionist. It may start with 'Toyota', 'Hey Toyota', "
        "or contain a clear direct request to Toyota.\n"
        "Rules:\n"
        "1. Return ONLY one JSON object with exactly these keys: addressed and cleaned_text.\n"
        "2. addressed is true only when the user clearly addresses Toyota; otherwise false.\n"
        "3. When addressed is true, cleaned_text is only the user's request, with obvious "
        "speech-to-text errors and punctuation tidied. Do not answer it, add meaning, or "
        "invent a request. Keep requests such as asking to talk to Mazda directed to Toyota.\n"
        "4. When addressed is false, cleaned_text must be an empty string.\n"
        "5. Never execute or describe an action.\n\n"
        f"Transcript: {json.dumps(transcript, ensure_ascii=False)}"
    )


def parse_receptionist_reply(reply: str) -> dict:
    """Strictly parse the policy response; malformed data fails closed."""
    fail = {"addressed": False, "cleaned_text": ""}
    if not reply:
        return fail
    try:
        value = json.loads(reply.strip())
    except (TypeError, json.JSONDecodeError):
        return fail
    if not isinstance(value, dict) or set(value) != {"addressed", "cleaned_text"}:
        return fail
    addressed = value["addressed"]
    cleaned = value["cleaned_text"]
    if not isinstance(addressed, bool) or not isinstance(cleaned, str):
        return fail
    cleaned = cleaned.strip()
    if addressed and not cleaned:
        return fail
    if not addressed and cleaned:
        return fail
    return {"addressed": addressed, "cleaned_text": cleaned}


class LettaReceptionistIntentStrategy(ReceptionistIntentStrategy):
    def __init__(self, client, agent_id, clear_history=True):
        self.client = client
        self.agent_id = agent_id
        self.clear_history = clear_history

    def evaluate(self, transcript: str) -> dict:
        if not transcript or not transcript.strip() or not self.agent_id:
            return {"addressed": False, "cleaned_text": ""}
        try:
            if self.clear_history:
                self.client.clear_messages(self.agent_id)
            response = self.client.send_message(
                self.agent_id, build_receptionist_prompt(transcript))
            return parse_receptionist_reply(extract_assistant_text(response))
        except Exception:
            return {"addressed": False, "cleaned_text": ""}


def build_receptionist_strategy() -> ReceptionistIntentStrategy:
    if config.RECEPTIONIST_INTENT_MODE == "deterministic":
        return DeterministicReceptionistIntentStrategy()
    if config.RECEPTIONIST_INTENT_MODE != "letta":
        raise ValueError(
            "unsupported receptionist intent mode: "
            f"{config.RECEPTIONIST_INTENT_MODE}"
        )

    from .letta_client import LettaClient

    client = LettaClient(config.LETTA_BASE_URL)
    agent_id = config.CLEANUP_AGENT_ID or client.resolve_agent_id(config.CLEANUP_AGENT_NAME)
    return LettaReceptionistIntentStrategy(client, agent_id)
