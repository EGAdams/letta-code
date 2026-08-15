"""Ports for the note-command channel (ABCs = the agreements).

Three separate jobs, three separate small interfaces — a client that only needs
to ask "is this instruction finished yet?" must not be forced to depend on how
notes are written to disk.

Concrete Letta/filesystem implementations live alongside in `note_*.py`; the
only place they are constructed is `note_factory.py`.
"""
from abc import ABC, abstractmethod

from .note_models import (
    CommandCompleteness,
    NoteCommandIntent,
    NoteEditRequest,
    PartialVoiceCommand,
    SavedNote,
)


class CommandCompletenessStrategy(ABC):
    """Decides whether accumulated speech is a finished instruction yet.

    Implementations MUST fail closed: any error, timeout, or unparseable reply
    returns `CommandCompleteness.incomplete(...)`. Waiting costs the user a
    pause; acting on half an instruction corrupts their note.
    """

    @abstractmethod
    def assess(self, partial: PartialVoiceCommand) -> CommandCompleteness:
        ...


class NoteCommandInterpreter(ABC):
    """Turns one completed instruction plus the current note into an intent.

    Knows nothing about speech recognition — a typed command and a spoken one
    produce the same `NoteEditRequest`.
    """

    @abstractmethod
    def interpret(self, request: NoteEditRequest) -> NoteCommandIntent:
        ...


class NoteRepository(ABC):
    """Persists a finished note."""

    @abstractmethod
    def save(self, note: str, filename: str = "") -> SavedNote:
        """Write `note`. A blank `filename` means the repository names it."""
        ...
