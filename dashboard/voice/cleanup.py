"""Transcript cleanup (Strategy) via a small, fast Letta agent.

whisper hears "Friday"; primed with the real agent names, the cleanup agent
rewrites it to "Frita" before the main agent sees it. Any failure falls back to
the raw transcript so a cleanup hiccup never blocks the user.
"""
from abc import ABC, abstractmethod

from . import config


class CleanupStrategy(ABC):
    @abstractmethod
    def clean(self, transcript: str) -> str:
        ...


def build_cleanup_prompt(transcript, known_names):
    names = ", ".join(known_names) if known_names else "(none provided)"
    return (
        "You clean up raw speech-to-text transcripts before they reach another agent.\n"
        "Rules:\n"
        "1. Fix obvious speech-to-text errors and punctuation.\n"
        "2. Correct agent names to the closest known agent when the intent is clear.\n"
        f"   Known agents: {names}.\n"
        "3. Do NOT add meaning, answer, or comment. Return ONLY the cleaned text.\n\n"
        f'Transcript: "{transcript}"'
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


class LettaAgentCleanup(CleanupStrategy):
    def __init__(self, client, agent_id, known_names=None, clear_history=True):
        self.client = client
        self.agent_id = agent_id
        self.known_names = known_names or []
        self.clear_history = clear_history

    def clean(self, transcript: str) -> str:
        if not transcript or not transcript.strip():
            return transcript
        try:
            if self.clear_history:
                self.client.clear_messages(self.agent_id)
            prompt = build_cleanup_prompt(transcript, self.known_names)
            response = self.client.send_message(self.agent_id, prompt)
            cleaned = extract_assistant_text(response)
            return cleaned or transcript
        except Exception:
            return transcript  # raw fallback


def build_cleanup() -> CleanupStrategy:
    from .letta_client import LettaClient

    client = LettaClient(config.LETTA_BASE_URL)
    agent_id = config.CLEANUP_AGENT_ID or client.resolve_agent_id(config.CLEANUP_AGENT_NAME)
    return LettaAgentCleanup(client, agent_id, known_names=config.KNOWN_AGENT_NAMES)
