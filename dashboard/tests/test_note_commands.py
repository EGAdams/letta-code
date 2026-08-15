"""Tests for the note-command channel.

The headline case is the one from the feature request: "Put a" must wait, and
"Put a period at the end" must execute.
"""
import datetime

import pytest
from pydantic import ValidationError

from voice.note_completeness import (
    LettaCommandCompletenessStrategy,
    build_completeness_prompt,
    parse_completeness_reply,
)
from voice.note_interpreter import (
    LettaNoteCommandInterpreter,
    build_interpreter_prompt,
    parse_interpreter_reply,
)
from voice.note_models import (
    CompletedVoiceCommand,
    NoteCommandRejected,
    NoteEditRequest,
    NoteRevision,
    NoteSaveRequest,
    PartialVoiceCommand,
)
from voice.note_repository import FilesystemNoteRepository, slugify
from voice.note_service import NoteCommandService


class FakeClient:
    """Stands in for LettaClient with the same three methods."""

    def __init__(self, reply="", fail=False):
        self.reply = reply
        self.fail = fail
        self.cleared = []
        self.sent = []

    def clear_messages(self, agent_id):
        self.cleared.append(agent_id)

    def send_message(self, agent_id, prompt):
        if self.fail:
            raise RuntimeError("letta down")
        self.sent.append((agent_id, prompt))
        return {
            "messages": [{"message_type": "assistant_message", "content": self.reply}]
        }


# ── Models ────────────────────────────────────────────────────────────────────


def test_partial_command_knows_when_nothing_has_been_said():
    assert PartialVoiceCommand(text="   ").is_empty
    assert not PartialVoiceCommand(text="Put a").is_empty


def test_completed_command_rejects_blank_text():
    with pytest.raises(ValidationError):
        CompletedVoiceCommand(text="   ")


def test_edit_request_rejects_a_blank_command():
    with pytest.raises(ValidationError):
        NoteEditRequest(note="Some note", command="  ")


# ── Completeness detector ─────────────────────────────────────────────────────


def test_completeness_prompt_carries_the_text_and_forbids_executing_it():
    prompt = build_completeness_prompt("Put a")
    assert "Put a" in prompt
    assert "exactly these keys" in prompt
    assert "Do NOT carry out" in prompt


def test_partial_instruction_is_not_complete():
    decision = parse_completeness_reply(
        '{"complete": false, "reason": "trails off, no object"}'
    )
    assert decision.complete is False
    assert decision.reason == "trails off, no object"


def test_whole_instruction_is_complete():
    assert parse_completeness_reply('{"complete": true, "reason": "whole"}').complete


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "Sure, I'll put a period at the end.",
        '{"complete": true}',
        '{"complete": "yes", "reason": "x"}',
        '{"complete": true, "reason": "x", "extra": 1}',
    ],
)
def test_malformed_completeness_replies_fail_closed(reply):
    assert parse_completeness_reply(reply).complete is False


def test_completeness_strategy_never_calls_out_for_empty_speech():
    client = FakeClient(reply='{"complete": true, "reason": "x"}')
    strategy = LettaCommandCompletenessStrategy(client, "agent-1")
    assert strategy.assess(PartialVoiceCommand(text="  ")).complete is False
    assert client.sent == []


def test_completeness_strategy_fails_closed_when_letta_is_down():
    strategy = LettaCommandCompletenessStrategy(FakeClient(fail=True), "agent-1")
    decision = strategy.assess(PartialVoiceCommand(text="Put a period at the end"))
    assert decision.complete is False
    assert decision.reason == "detector unavailable"


# ── Interpreter ───────────────────────────────────────────────────────────────


def test_interpreter_prompt_carries_both_the_note_and_the_command():
    prompt = build_interpreter_prompt(
        NoteEditRequest(
            note="Today Roy and I worked on the scoreboard",
            command="Put a period at the end",
        )
    )
    assert "Today Roy and I worked on the scoreboard" in prompt
    assert "Put a period at the end" in prompt


def test_edit_intent_carries_the_whole_revised_note():
    intent = parse_interpreter_reply(
        '{"action": "edit", "revised_note": "Today Roy and I worked on the '
        'scoreboard.", "filename": "", "reason": "added period"}'
    )
    assert isinstance(intent, NoteRevision)
    assert intent.revised_note == "Today Roy and I worked on the scoreboard."


def test_save_intent_keeps_the_name_the_user_asked_for():
    intent = parse_interpreter_reply(
        '{"action": "save", "revised_note": "", "filename": "meeting notes", '
        '"reason": "explicit name"}'
    )
    assert isinstance(intent, NoteSaveRequest)
    assert intent.filename == "meeting notes"


def test_save_without_a_stated_name_leaves_the_choice_to_the_repository():
    intent = parse_interpreter_reply(
        '{"action": "save", "revised_note": "", "filename": "", "reason": "no name"}'
    )
    assert isinstance(intent, NoteSaveRequest)
    assert intent.filename == ""


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I put a period at the end for you!",
        '{"action": "edit", "revised_note": "", "filename": "", "reason": "x"}',
        '{"action": "edit", "revised_note": "x", "filename": "y", "reason": "x"}',
        '{"action": "save", "revised_note": "x", "filename": "y", "reason": "x"}',
        '{"action": "delete_everything", "revised_note": "", "filename": "", "reason": ""}',
        '{"action": "edit", "revised_note": "x"}',
    ],
)
def test_malformed_interpreter_replies_leave_the_note_alone(reply):
    assert isinstance(parse_interpreter_reply(reply), NoteCommandRejected)


def test_interpreter_fails_closed_when_letta_is_down():
    interpreter = LettaNoteCommandInterpreter(FakeClient(fail=True), "agent-1")
    intent = interpreter.interpret(NoteEditRequest(note="n", command="c"))
    assert isinstance(intent, NoteCommandRejected)


# ── Repository ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("meeting notes", "meeting-notes"),
        ("../../etc/passwd", "etc-passwd"),
        ("Scoreboard: Roy & I", "scoreboard-roy-i"),
        ("///", ""),
        ("", ""),
    ],
)
def test_slugify_makes_a_model_supplied_name_safe(raw, expected):
    assert slugify(raw) == expected


def _repo(tmp_path):
    return FilesystemNoteRepository(
        directory=str(tmp_path),
        clock=lambda: datetime.datetime(2026, 8, 12),
    )


def test_save_writes_a_dated_markdown_file(tmp_path):
    saved = _repo(tmp_path).save("Today Roy and I worked on the scoreboard.", "meeting notes")
    assert saved.filename == "2026-08-12_meeting-notes.md"
    assert (tmp_path / saved.filename).read_text() == (
        "Today Roy and I worked on the scoreboard.\n"
    )


def test_save_falls_back_to_a_generic_stem_when_no_name_survives(tmp_path):
    assert _repo(tmp_path).save("body", "///").filename == "2026-08-12_note.md"


def test_saving_twice_never_overwrites_the_first_note(tmp_path):
    repo = _repo(tmp_path)
    first = repo.save("one", "notes")
    second = repo.save("two", "notes")
    assert first.filename != second.filename
    assert (tmp_path / first.filename).read_text() == "one\n"
    assert (tmp_path / second.filename).read_text() == "two\n"


def test_a_path_traversing_name_stays_inside_the_notes_directory(tmp_path):
    saved = _repo(tmp_path).save("body", "../../../etc/passwd")
    assert saved.filename == "2026-08-12_etc-passwd.md"
    assert (tmp_path / saved.filename).exists()


# ── Service ───────────────────────────────────────────────────────────────────


class FakeCompleteness:
    def __init__(self, decision):
        self.decision = decision

    def assess(self, partial):
        return self.decision


class FakeInterpreter:
    def __init__(self, intent):
        self.intent = intent
        self.seen = []

    def interpret(self, request):
        self.seen.append(request)
        return self.intent


class FakeRepository:
    def __init__(self, saved=None, error=None):
        self.saved = saved
        self.error = error
        self.calls = []

    def save(self, note, filename=""):
        self.calls.append((note, filename))
        if self.error:
            raise self.error
        return self.saved


def _service(intent, repository=None):
    return NoteCommandService(
        completeness=FakeCompleteness(None),
        interpreter=FakeInterpreter(intent),
        repository=repository or FakeRepository(),
    )


def test_an_edit_returns_the_revised_note():
    outcome = _service(NoteRevision(revised_note="Note.")).apply(
        NoteEditRequest(note="Note", command="put a period at the end")
    )
    assert outcome.kind == "edit"
    assert outcome.note == "Note."


def test_a_rejected_command_returns_the_note_unchanged():
    outcome = _service(NoteCommandRejected(reason="not understood")).apply(
        NoteEditRequest(note="Note", command="flurb the widget")
    )
    assert outcome.kind == "none"
    assert outcome.note == "Note"
    assert outcome.saved is None


def test_saving_an_empty_note_is_refused_before_touching_the_repository():
    repository = FakeRepository()
    outcome = _service(NoteSaveRequest(filename="x"), repository).apply(
        NoteEditRequest(note="   ", command="save this")
    )
    assert outcome.kind == "none"
    assert repository.calls == []


def test_a_save_reports_where_the_note_landed():
    from voice.note_models import SavedNote

    repository = FakeRepository(
        saved=SavedNote(filename="2026-08-12_meeting-notes.md", path="/n/x.md")
    )
    outcome = _service(NoteSaveRequest(filename="meeting notes"), repository).apply(
        NoteEditRequest(note="Body", command="save this as meeting notes")
    )
    assert outcome.kind == "save"
    assert outcome.note == "Body"
    assert outcome.saved.filename == "2026-08-12_meeting-notes.md"
    assert "2026-08-12_meeting-notes.md" in outcome.message


def test_a_failed_write_leaves_the_note_intact_and_says_so():
    repository = FakeRepository(error=OSError("disk full"))
    outcome = _service(NoteSaveRequest(filename="x"), repository).apply(
        NoteEditRequest(note="Body", command="save this")
    )
    assert outcome.kind == "none"
    assert outcome.note == "Body"
    assert "disk full" in outcome.message


# ── Composition root ──────────────────────────────────────────────────────────


def test_an_unreachable_letta_yields_a_service_that_waits_instead_of_raising():
    from voice.note_factory import build_note_command_service

    class DeadClient(FakeClient):
        def resolve_agent_id(self, name):
            raise OSError("connection refused")

    service, agent_id = build_note_command_service(client=DeadClient())
    assert agent_id == ""
    # Fail closed on both halves rather than blowing up the request handler.
    assert service.assess(PartialVoiceCommand(text="Put a period at the end")).complete is False
    outcome = service.apply(NoteEditRequest(note="Body", command="save this"))
    assert outcome.kind == "none"
    assert outcome.note == "Body"


def test_a_service_built_while_letta_was_down_is_not_cached(monkeypatch):
    import voice.note_factory as factory

    monkeypatch.setattr(factory, "_CACHED", None)
    calls = []

    def fake_build():
        calls.append(1)
        return object(), ""

    monkeypatch.setattr(factory, "build_note_command_service", fake_build)
    factory.note_command_service()
    factory.note_command_service()
    assert len(calls) == 2


