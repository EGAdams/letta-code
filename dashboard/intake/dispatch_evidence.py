"""Did the intake dispatch actually land in Mazda's conversation?

Asked only on the error path. Letta keeps a non-streaming messages POST open
while the agent works, so a document intake can outlive our HTTP timeout even
though Letta accepted it -- treating every failed POST as a failed dispatch
would report a scan as broken while Mazda was busy filing it correctly.

The check that existed for that read the conversation object and returned true
for **any** `in_context_message_ids` entry, on the stated premise that "the
conversation is created empty, so any in-context message id is unambiguous
acknowledgement of this dispatch". That premise was never true. A freshly
created conversation already carries its system prompt, so the check answered
"accepted" for every conversation that exists at all.

What that cost, 2026-08-19: the dispatch POST for the Window Scanner intake was
rejected with HTTP 429. Nothing was queued. The probe saw the system prompt,
reported the dispatch accepted, and the scan was recorded `processing`. The
transport-failure path -- which exists precisely to make this visible and
retryable -- never ran. The scan hung until the Trainer noticed 15 minutes
later and correctly called it an infrastructure problem: "the conversation
exists but received nothing after its system prompt".

So the question is asked properly here: not "does this conversation contain
anything" but "does it contain anything WE put there". Each intake gets its own
isolated conversation, so a single non-system message is exactly that evidence.

Failure to read the conversation counts as no evidence. A scan visibly reported
as failed can be run again; one silently recorded as in-flight cannot, and that
is the failure this module exists to prevent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from contracts import StrictModel

#: Letta's own name for the prompt every conversation is born with. It is not
#: evidence of anything -- it is there before any dispatch is attempted.
SYSTEM_MESSAGE_TYPE = 'system_message'


class ConversationMessage(StrictModel):
    """One message, read tolerantly.

    Only the two fields that decide whether this message is the system prompt.
    Letta's message payload is large and versioned on its own schedule; binding
    to more of it would make an unrelated upstream field rename look like a
    failed dispatch.
    """

    message_type: str = ''
    role: str = ''

    @classmethod
    def from_row(cls, row: Any) -> 'ConversationMessage':
        if not isinstance(row, Mapping):
            return cls()
        return cls(
            message_type=str(row.get('message_type') or ''),
            role=str(row.get('role') or ''),
        )

    @property
    def is_system_prompt(self) -> bool:
        return self.message_type == SYSTEM_MESSAGE_TYPE or self.role == 'system'


class DispatchEvidence(StrictModel):
    """What one conversation's messages say about whether a dispatch landed."""

    messages: tuple[ConversationMessage, ...] = ()

    @classmethod
    def from_payload(cls, payload: Any) -> 'DispatchEvidence':
        """Read Letta's conversation-messages response.

        Accepts a bare list or an object wrapping one, because which of the two
        arrives has changed across Letta versions and neither shape means
        anything different. Anything else reads as no evidence.
        """
        rows: Any = payload
        if isinstance(payload, Mapping):
            rows = payload.get('messages')
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            return cls()
        # Only rows we could actually read count. A row that is not a mapping
        # carries no information, and letting it through as a blank message
        # would make it "not the system prompt" and therefore evidence -- the
        # same over-optimism as the check this replaced.
        return cls(messages=tuple(
            ConversationMessage.from_row(row)
            for row in rows if isinstance(row, Mapping)))

    @property
    def dispatch_landed(self) -> bool:
        """True only if something other than the system prompt is in there.

        Each intake gets its own conversation, so anything beyond the prompt it
        was born with came from our dispatch -- or from Mazda answering it,
        which is the same conclusion.
        """
        return any(not message.is_system_prompt for message in self.messages)
