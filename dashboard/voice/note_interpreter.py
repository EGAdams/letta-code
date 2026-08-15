"""Letta-backed NoteCommandInterpreter.

Runs once per *completed* instruction (the completeness detector is the gate),
and returns a validated intent rather than free prose:

    "put a period at the end"   -> NoteRevision(revised_note=...)
    "change Smith to Smythe"    -> NoteRevision(revised_note=...)
    "save this as meeting notes"-> NoteSaveRequest(filename="meeting notes")
    "save this"                 -> NoteSaveRequest(filename=<Toyota's choice>)
    anything unclear            -> NoteCommandRejected

Why the whole revised note rather than a structured diff: the instructions this
channel must handle ("move that sentence to the top", "delete that last
paragraph", "add a heading") do not share one edit primitive, and inventing a
mini edit language would fail on the first command that doesn't fit. The *kind*
of outcome is still an explicit, discriminated model — only the edit payload is
text.

Fails closed: an unparseable or unexpected reply leaves the note untouched.
"""
import json

from .cleanup import extract_assistant_text
from .note_models import (
    NoteCommandIntent,
    NoteCommandRejected,
    NoteEditRequest,
    NoteRevision,
    NoteSaveRequest,
)
from .note_ports import NoteCommandInterpreter

_ALLOWED_KEYS = {"action", "revised_note", "filename", "reason"}


def build_interpreter_prompt(request: NoteEditRequest) -> str:
    return (
        "You edit a plain-text note on the user's behalf. You are given the "
        "note's current text and one spoken instruction about it.\n"
        "Rules:\n"
        "1. Return ONLY one JSON object with exactly these keys: action, "
        "revised_note, filename, reason.\n"
        '2. action is "edit", "save", or "none".\n'
        '3. For "edit": revised_note is the note\'s COMPLETE new text after '
        "applying the instruction. Change only what the instruction asks for — "
        "keep every other word, line break, and spelling exactly as-is. "
        'filename must be "".\n'
        '4. For "save": the user asked to store the note. filename is a short '
        "descriptive name. If they named one, use it. If they did not, choose one "
        "from the note's actual subject matter. No extension, no path. "
        'revised_note must be "".\n'
        '5. For "none": you could not confidently carry out the instruction. '
        'revised_note and filename must both be "". Use this rather than guessing.\n'
        "6. Never answer the note's content, add commentary, or invent facts.\n"
        "7. reason is at most eight words.\n\n"
        f"Current note: {json.dumps(request.note, ensure_ascii=False)}\n"
        f"Instruction: {json.dumps(request.command, ensure_ascii=False)}"
    )


def parse_interpreter_reply(reply: str) -> NoteCommandIntent:
    """Strictly parse the interpreter's response; anything odd changes nothing."""
    if not reply:
        return NoteCommandRejected(reason="no reply")
    try:
        value = json.loads(reply.strip())
    except (TypeError, json.JSONDecodeError):
        return NoteCommandRejected(reason="unparseable reply")
    if not isinstance(value, dict) or set(value) != _ALLOWED_KEYS:
        return NoteCommandRejected(reason="unexpected reply shape")
    action = value["action"]
    revised = value["revised_note"]
    filename = value["filename"]
    reason = value["reason"]
    if not all(isinstance(v, str) for v in (action, revised, filename, reason)):
        return NoteCommandRejected(reason="wrong reply types")

    if action == "edit":
        # An "edit" that produced nothing is a malformed reply, not an
        # instruction to erase the user's note.
        if not revised.strip() or filename:
            return NoteCommandRejected(reason="empty or contradictory edit")
        return NoteRevision(revised_note=revised)
    if action == "save":
        if revised:
            return NoteCommandRejected(reason="contradictory save")
        return NoteSaveRequest(filename=filename.strip())
    return NoteCommandRejected(reason=reason.strip() or "not understood")


class LettaNoteCommandInterpreter(NoteCommandInterpreter):
    def __init__(self, client, agent_id, clear_history=True):
        self.client = client
        self.agent_id = agent_id
        self.clear_history = clear_history

    def interpret(self, request: NoteEditRequest) -> NoteCommandIntent:
        if not self.agent_id:
            return NoteCommandRejected(reason="no interpreter agent")
        try:
            if self.clear_history:
                self.client.clear_messages(self.agent_id)
            response = self.client.send_message(
                self.agent_id, build_interpreter_prompt(request)
            )
        except Exception:
            return NoteCommandRejected(reason="interpreter unavailable")
        return parse_interpreter_reply(extract_assistant_text(response))
