import { Status } from "../../interface-spec.js";

export const noteCommandSpec = {
  id: "note-command-channel",
  name: "Note Command Channel",
  group: "Shipped ports",
  tagline:
    "Four ports that turn spoken instructions into edits on a document. The newest and most complete slice.",
  status: Status.FINISHED,
  statusNote:
    "Complete end to end and verified live. 68 tests across seven files.",
  responsibility: [
    "Let someone dictate a note into one box and then speak instructions about it into another — 'put a period at the end', 'change Smith to Smythe', 'save this as meeting notes' — without having to speak unnaturally fast.",
    "Its defining decision is that command completeness is judged from the accumulated text, never from a silence timer. 'Put a' waits indefinitely; 'Put a period at the end' executes. That is what makes the interaction conversational.",
    "Four narrow ports rather than one: is the instruction finished (CommandCompletenessStrategy), what does it mean (NoteCommandInterpreter), where do notes get stored (NoteRepository), and what surface is being edited (NoteDocument). The editor never learns whether a command came from speech or the keyboard.",
  ],
  contract: {
    language: "text",
    code: `CommandCompletenessStrategy(ABC)   voice/note_ports.py
  assess(PartialVoiceCommand) -> CommandCompleteness {complete, reason}

NoteCommandInterpreter(ABC)
  interpret(NoteEditRequest) -> NoteRevision | NoteSaveRequest | NoteCommandRejected
                                (discriminated on "kind")

NoteRepository(ABC)
  save(note, filename="") -> SavedNote      "" means the repo names it

NoteDocument   js/abstract/note-document.interface.js
  getText() setText(text) appendText(text) element editable`,
    note: "All models are strict Pydantic (extra='forbid', frozen). An 'edit' carrying empty text is treated as a malformed reply, never as an instruction to blank the note.",
  },
  implementations: [
    {
      name: "LettaCommandCompletenessStrategy",
      kind: "current",
      file: "voice/note_completeness.py",
      note: "One strict-JSON call per finalized fragment.",
    },
    {
      name: "LettaNoteCommandInterpreter",
      kind: "current",
      file: "voice/note_interpreter.py",
      note: "Returns the whole revised note; the outcome kind is discriminated.",
    },
    {
      name: "FilesystemNoteRepository",
      kind: "current",
      file: "voice/note_repository.py",
      note: "Slugifies the model-supplied name, date-prefixes, and never overwrites.",
    },
    {
      name: "ReadOnlyNoteSurface / EditableTextareaSurface",
      kind: "current",
      file: "js/implementation/textarea-note-surfaces.js",
      note: "Two NoteDocument implementations; Toyota's note uses the read-only one.",
    },
    {
      name: "TranscriptSyncedNote",
      kind: "current",
      file: "js/implementation/transcript-synced-note.js",
      note: "Decorator resolving the two-writer problem between dictation and commands.",
    },
    {
      name: "HttpCompletenessDetector / HttpNoteCommandInterpreter",
      kind: "current",
      file: "js/implementation/http-note-command-services.js",
      note: "Browser adapters that validate responses and fail closed.",
    },
    {
      name: "Local completeness detector",
      kind: "planned",
      file: "—",
      note: "A non-LLM detector would remove one network round-trip per spoken fragment.",
    },
  ],
  dependencies: {
    usedBy: [
      "VoiceCommandChannel",
      "NoteCommandPanelRenderer",
      "Toyota's home-screen note",
    ],
    dependsOn: [
      "LettaClient (via the two strategies)",
      "filesystem (NOTES_DIR)",
      "POST /api/note-command-complete, /api/note-command-apply",
    ],
    note: "The layering is clean here: policy (VoiceCommandChannel, NoteCommandService) depends only on ports, and every concrete Letta/HTTP/filesystem detail sits in an adapter constructed at a composition root.",
  },
  developmentStatus: {
    done: [
      "The pause-and-resume behaviour works and is verified against a live agent: 'Put a' → incomplete, 'Put a period at the end' → applied.",
      "Toyota chooses a sensible filename when the user does not — verified live producing 2026-08-12_scoreboard-work.md.",
      "Every failure mode fails closed: malformed JSON, contradictory replies, an unreachable Letta, and a 401 all leave the note untouched.",
      "A model-supplied filename is slugified and date-prefixed, so path traversal cannot escape the notes directory, and saving twice never overwrites.",
      "The two-writer problem between dictation and commands is solved by a Decorator rather than by coupling the two paths.",
      "Typed and spoken commands take the identical path into the interpreter.",
    ],
    gaps: [
      "Every finalized speech fragment costs one LLM round-trip for the completeness check — the dominant latency and cost in the loop.",
      "A rejected command explains itself but cannot ask a clarifying question; 'Add a heading' is rejected rather than answered with 'what heading?'.",
      "No undo. An applied edit replaces the note with no history.",
      "BLOCKED in production by the shared worker agent's dead LLM handle.",
    ],
  },
  tests: {
    files: [
      {
        path: "dashboard/tests/test_note_commands.py",
        count: 27,
        proves:
          "Model validation, both strict parsers' fail-closed behaviour, filename slugification and traversal safety, non-overwriting saves, service policy for empty notes and failed writes, and that an unreachable Letta never raises into the handler.",
      },
      {
        path: "js/tests/voice-command-channel.test.js",
        count: 13,
        proves:
          "The pause behaviour, interim results never being assessed, dedupe of repeated finals, ordering under overlapping speech, and that rejection preserves state.",
      },
      {
        path: "js/tests/textarea-note-surfaces.test.js",
        count: 8,
        proves:
          "Read-only vs editable surfaces, white-on-black note styling, and that an external edit survives the next dictated sentence.",
      },
      {
        path: "js/tests/note-command-panel.test.js",
        count: 7,
        proves: "The DOM binding and that Clear never touches the note.",
      },
      {
        path: "js/tests/http-note-command-services.test.js",
        count: 7,
        proves:
          "Both browser adapters set their own timeouts and fail closed on transport errors.",
      },
      {
        path: "js/tests/note-command-contracts.test.js",
        count: 4,
        proves:
          "Runtime validation of both response shapes, including that an empty 'edit' is rejected.",
      },
      {
        path: "js/tests/input-options-note-surface.test.js",
        count: 4,
        proves:
          "Sending never wipes a read-only note, while an editable box still clears.",
      },
    ],
    untested: [
      "No test covers a completeness check that hangs rather than fails.",
      "Nothing asserts behaviour when the note is very large — the whole note is sent on every command.",
    ],
    next: [
      "A hung-detector test using a never-settling promise.",
      "A test for a large note, once a size limit is decided.",
    ],
  },
  diagrams: [
    {
      title: "Four ports, one flow",
      caption:
        "The interpreter returns a discriminated outcome, so the service branches on a validated tag rather than sniffing which optional keys are present.",
      code: `flowchart TB
  Speech([Spoken command])
  TB[TranscriptBuffer]
  VCC[VoiceCommandChannel]
  CC{{CommandCompletenessStrategy}}
  NI{{NoteCommandInterpreter}}
  NCS[NoteCommandService]
  NR{{NoteRepository}}
  ND{{NoteDocument}}
  Speech --> TB --> VCC
  VCC -->|"every final fragment"| CC
  CC -->|"complete"| VCC
  VCC -->|"once"| NCS
  NCS --> NI
  NI -->|"kind=edit"| ND
  NI -->|"kind=save"| NR
  NI -->|"kind=none"| VCC`,
    },
    {
      title: "The two-writer problem",
      caption:
        "Without TranscriptSyncedNote, the buffer's stale copy silently undoes Toyota's edit on the next dictated sentence.",
      code: `sequenceDiagram
  participant Buf as TranscriptBuffer
  participant Synced as TranscriptSyncedNote
  participant Surf as ReadOnlyNoteSurface

  Buf->>Surf: "worked on the scoreboard"
  Synced->>Synced: command applies an edit
  Synced->>Buf: resync("worked on the scoreboard.")
  Synced->>Surf: setText("...scoreboard.")
  Buf->>Surf: + "Then we went home"
  Note over Buf,Surf: the period survives the<br/>next dictated sentence`,
    },
  ],
  nextWork: [
    "Add a cheap local pre-filter so obviously-incomplete fragments skip the LLM round-trip entirely.",
    "Let a rejected command ask one clarifying question instead of just refusing.",
    "Add undo — keep the previous note text and a 'revert that' command.",
    "Add the hung-detector test.",
  ],
};
