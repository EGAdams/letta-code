"""NoteCommandService — the application facade over the three note ports.

Holds the only policy in the flow: *what does an interpreted intent actually do
to the note?* It talks to ports, never to Letta or the filesystem, so the whole
thing is unit-testable with fakes and any port can be swapped at the composition
root without touching this file.

The browser calls exactly two operations:

    assess(partial)  -> CommandCompleteness   "should I wait for more speech?"
    apply(request)   -> NoteCommandOutcome    "here is the note's new text"
"""
from .note_models import (
    CommandCompleteness,
    NoteCommandOutcome,
    NoteCommandRejected,
    NoteEditRequest,
    NoteRevision,
    NoteSaveRequest,
    PartialVoiceCommand,
)
from .note_ports import (
    CommandCompletenessStrategy,
    NoteCommandInterpreter,
    NoteRepository,
)


class NoteCommandService:
    def __init__(
        self,
        completeness: CommandCompletenessStrategy,
        interpreter: NoteCommandInterpreter,
        repository: NoteRepository,
    ):
        self._completeness = completeness
        self._interpreter = interpreter
        self._repository = repository

    def assess(self, partial: PartialVoiceCommand) -> CommandCompleteness:
        return self._completeness.assess(partial)

    def apply(self, request: NoteEditRequest) -> NoteCommandOutcome:
        intent = self._interpreter.interpret(request)

        if isinstance(intent, NoteRevision):
            return NoteCommandOutcome(kind="edit", note=intent.revised_note)

        if isinstance(intent, NoteSaveRequest):
            if not request.note.strip():
                return NoteCommandOutcome.rejected(
                    request.note, "There's nothing in the note to save yet."
                )
            try:
                saved = self._repository.save(request.note, intent.filename)
            except OSError as exc:
                return NoteCommandOutcome.rejected(
                    request.note, f"Could not save the note: {exc}"
                )
            return NoteCommandOutcome(
                kind="save",
                note=request.note,
                saved=saved,
                message=f"Saved as {saved.filename}.",
            )

        assert isinstance(intent, NoteCommandRejected)
        return NoteCommandOutcome.rejected(
            request.note, intent.reason or "I didn't follow that."
        )
