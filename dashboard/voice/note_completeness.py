"""Letta-backed CommandCompletenessStrategy.

Answers one question and nothing else: *does the accumulated command text
already express a finished instruction?*

    "Put a"                    -> complete: false   (keep listening)
    "Put a period at the end"  -> complete: true    (hand to the interpreter)

Deciding this from the text — rather than from a silence timer — is what lets
the user pause mid-sentence without Toyota jumping the gun.

Fails closed in every failure mode: a network error, a timeout, prose instead of
JSON, or an unexpected key all resolve to "not complete yet".
"""
import json

from .cleanup import extract_assistant_text
from .note_models import CommandCompleteness, PartialVoiceCommand
from .note_ports import CommandCompletenessStrategy


def build_completeness_prompt(command_text: str) -> str:
    return (
        "You judge whether a dictated instruction is FINISHED. The user is "
        "speaking a command that edits a text document, and they pause often "
        "mid-sentence.\n"
        "Rules:\n"
        "1. Return ONLY one JSON object with exactly these keys: complete and reason.\n"
        "2. complete is true only when the text on its own is a whole, actionable "
        "instruction. If it trails off, is missing its object, or clearly expects "
        "more words, complete is false.\n"
        "3. Do NOT carry out the instruction, answer it, or guess the missing words.\n"
        "4. reason is at most eight words explaining the verdict.\n"
        "Examples:\n"
        '  "Put a" -> {"complete": false, "reason": "trails off, no object"}\n'
        '  "Put a period at the end" -> {"complete": true, "reason": "whole instruction"}\n'
        '  "Change Smith" -> {"complete": false, "reason": "missing replacement"}\n'
        '  "Save this" -> {"complete": true, "reason": "whole instruction"}\n\n'
        f"Instruction so far: {json.dumps(command_text, ensure_ascii=False)}"
    )


def parse_completeness_reply(reply: str) -> CommandCompleteness:
    """Strictly parse the detector's response; anything odd means 'keep waiting'."""
    if not reply:
        return CommandCompleteness.incomplete("no reply")
    try:
        value = json.loads(reply.strip())
    except (TypeError, json.JSONDecodeError):
        return CommandCompleteness.incomplete("unparseable reply")
    if not isinstance(value, dict) or set(value) != {"complete", "reason"}:
        return CommandCompleteness.incomplete("unexpected reply shape")
    complete = value["complete"]
    reason = value["reason"]
    if not isinstance(complete, bool) or not isinstance(reason, str):
        return CommandCompleteness.incomplete("wrong reply types")
    return CommandCompleteness(complete=complete, reason=reason.strip())


class LettaCommandCompletenessStrategy(CommandCompletenessStrategy):
    def __init__(self, client, agent_id, clear_history=True):
        self.client = client
        self.agent_id = agent_id
        self.clear_history = clear_history

    def assess(self, partial: PartialVoiceCommand) -> CommandCompleteness:
        if partial.is_empty:
            return CommandCompleteness.incomplete("nothing said yet")
        if not self.agent_id:
            return CommandCompleteness.incomplete("no completeness agent")
        try:
            if self.clear_history:
                self.client.clear_messages(self.agent_id)
            response = self.client.send_message(
                self.agent_id, build_completeness_prompt(partial.text.strip())
            )
        except Exception:
            return CommandCompleteness.incomplete("detector unavailable")
        return parse_completeness_reply(extract_assistant_text(response))
