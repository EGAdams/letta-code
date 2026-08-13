"""Data shapes for the voice note-command channel (Pydantic = the seam).

The note-command channel has two conversations running side by side:

* the **note** — dictated speech that streams into Toyota's read-only document;
* the **command channel** — spoken instructions *about* that note
  ("put a period at the end", "save this as meeting notes").

Every concept that crosses a boundary in that flow gets a model here, so no
component has to guess what a bare ``dict`` or ``str`` means. Nothing in this
module imports Letta, urllib, or the filesystem — it is pure shape plus
validation, per the abstract/implementation split the rest of the dashboard
already follows.
"""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    """Reject unknown keys everywhere: a model reply that invents a field is a
    malformed reply, and this channel edits the user's document."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PartialVoiceCommand(_Strict):
    """Whatever the command channel has accumulated so far.

    This is deliberately *not* "the last speech fragment" — completeness is
    judged on the whole accumulated instruction, which is the entire point of
    letting the user pause mid-sentence.
    """

    text: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class CompletedVoiceCommand(_Strict):
    """A partial command the completeness detector has accepted as finished."""

    text: str

    @field_validator("text")
    @classmethod
    def _must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a completed command cannot be blank")
        return value.strip()


class CommandCompleteness(_Strict):
    """The completeness detector's verdict on a PartialVoiceCommand."""

    complete: bool = False
    reason: str = ""

    @classmethod
    def incomplete(cls, reason: str = "") -> "CommandCompleteness":
        """The fail-closed answer. Waiting for more speech is always safe;
        executing a half-heard instruction against the note is not."""
        return cls(complete=False, reason=reason)


class NoteDocumentState(_Strict):
    """The note as it currently reads."""

    text: str = ""


class NoteEditRequest(_Strict):
    """One completed instruction paired with the note it applies to."""

    note: str = ""
    command: str

    @field_validator("command")
    @classmethod
    def _command_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a note-edit request needs a command")
        return value.strip()


# ── What the interpreter decided to do ────────────────────────────────────────
# Discriminated on `kind` so callers branch on a validated tag rather than
# sniffing which optional keys happen to be present.


class NoteRevision(_Strict):
    """Rewrite the note. `revised_note` is the note's complete new text."""

    kind: Literal["edit"] = "edit"
    revised_note: str


class NoteSaveRequest(_Strict):
    """Persist the note. Toyota picks `filename` when the user didn't say one."""

    kind: Literal["save"] = "save"
    filename: str = ""


class NoteCommandRejected(_Strict):
    """The instruction was not understood. The note is left untouched."""

    kind: Literal["none"] = "none"
    reason: str = ""


NoteCommandIntent = Annotated[
    Union[NoteRevision, NoteSaveRequest, NoteCommandRejected],
    Field(discriminator="kind"),
]


class SavedNote(_Strict):
    """Where a save actually landed."""

    filename: str
    path: str


class NoteCommandOutcome(_Strict):
    """The single response shape the browser receives for an applied command.

    `note` is always the text the document should now show — unchanged when the
    command was rejected — so the caller never has to decide whether to keep its
    old copy.
    """

    kind: Literal["edit", "save", "none"]
    note: str = ""
    saved: Optional[SavedNote] = None
    message: str = ""

    @classmethod
    def rejected(cls, note: str, message: str = "") -> "NoteCommandOutcome":
        return cls(kind="none", note=note, message=message)
