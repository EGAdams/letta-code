import { Status } from "../../interface-spec.js";

export const conversationCoordinatorSpec = {
  id: "conversation-coordinator",
  name: "ConversationCoordinator",
  group: "Planned core",
  tagline:
    "Typed Mediator design for streamed agent text, sentence-level speech, and interruption.",
  status: Status.PARTIAL,
  statusNote:
    "The typed dialogue coordinator contract and transport design now live in js/abstract/conversation_coordinator/. Runtime behavior is the next TDD slice.",
  responsibility: [
    "Coordinate one finalized user turn into exactly one agent run, and make sure overlapping speech never produces overlapping responses. It is the Mediator between capture, the agent, and output.",
    "The shipped VoiceCommandChannel already owns a meaningful piece of this: it serialises work onto a promise chain, dedupes identical finalized transcripts, and decides when an instruction is complete enough to act on. That last decision — completeness judged from accumulated text rather than a silence timer — is the part worth keeping in any rebuild.",
    "The new typed contract now defines dialogue coordination without DOM, HTTP, Letta, or audio-provider dependencies. Runtime turn coordination still lives in renderer closures until the next TDD slice implements and adopts the contract.",
  ],
  contract: {
    language: "ts",
    code: `ConversationCoordinatorPort
  js/abstract/conversation_coordinator/src/conversation-coordinator.ts

  start(turn, { agentName, speak }) -> Promise<ConversationTurnOutcome>
  interrupt()                       -> GenerationId | null
  close()                           -> void

  injected collaborators:
    agent                ConversationAgentPort
    session              VoiceSessionPort
    spokenOutputPolicy   SpokenOutputPolicyPort
    sentenceSegmenter    SentenceSegmenterPort
    speechQueue          SpeechQueuePort
    observer             ConversationCoordinatorObserver

Existing note-edit mediator:
  VoiceCommandChannel.handleSpeech(text, isFinal) -> Promise`,
    note: "The coordinator knows normalized events, generations, sentences, and queue order. Concrete DOM, HTTP, Letta wire, and audio-provider behavior is injected.",
  },
  implementations: [
    {
      name: "VoiceCommandChannel",
      kind: "current",
      file: "js/abstract/voice-command-channel.js",
      note: "Coordinates note-edit commands. Serialised queue, dedupe, completeness gating.",
    },
    {
      name: "NoteCommandPanelRenderer",
      kind: "current",
      file: "js/implementation/note-command-panel.js",
      note: "Binds the channel to DOM and a ContinuousListener. Holds no policy.",
    },
    {
      name: "ConversationCoordinator",
      kind: "planned",
      file: "js/abstract/conversation_coordinator/src/conversation-coordinator.ts",
      note: "Typed Mediator contract for agent events, generation fencing, sentence segmentation, ordered speech, observers, and interruption. Implementation is intentionally waiting on failing tests.",
    },
  ],
  dependencies: {
    usedBy: [
      "InputOptionsRenderer (planned adoption)",
      "ChatDetailRenderer (planned adoption)",
      "VoiceCommandChannel remains the note-edit coordinator",
    ],
    dependsOn: [
      "ConversationAgentPort — normalized async agent events",
      "VoiceSessionPort — state and generation fencing",
      "SpokenOutputPolicyPort — current public assistant text only",
      "SentenceSegmenterPort — deterministic sentence boundary Strategy",
      "SpeechQueuePort — ordered preparation, playback, and cancellation",
      "ConversationCoordinatorObserver — UI and timing notifications",
    ],
    note: "All collaborators are injected ports. Streaming HTTP, Letta wire parsing, DOM updates, and speech-provider details stay in concrete adapters outside the coordinator.",
  },
  developmentStatus: {
    done: [
      "The dialogue Mediator has a strict TypeScript contract and reuses the existing ConversationTurn, AgentEvent, and VoiceSession types.",
      "The first-sentence, streaming transport, and barge-in flows are documented as Mermaid diagrams beside the module.",
      "The transport design uses the CLI's existing stream-json output and requires browser abort to terminate the server-side process group.",
      "Work is serialised on a promise chain, so an in-flight edit cannot interleave with the next speech fragment.",
      "Identical finalized text is never assessed twice — important because the recognizer re-flushes its tail on every silence restart.",
      "Completeness is judged from accumulated text via an injected detector, never from a silence timeout.",
      "A rejected command leaves both the note and the command text alone, so the user can reword and retry.",
      "Errors from either collaborator surface as status without wedging the queue.",
    ],
    gaps: [
      "The dialogue coordinator has a typed contract and diagrams but no runtime implementation yet.",
      "There is no streaming dashboard endpoint or browser adapter yet; the current Letta adapter still yields one complete answer.",
      "The sentence boundary Strategy and ordered speech queue are contracts only.",
      "Input Options and Chat still coordinate turns in renderer closures.",
    ],
  },
  tests: {
    files: [
      {
        path: "js/tests/voice-command-channel.test.js",
        count: 13,
        proves:
          "The headline pause behaviour ('Put a' waits, 'Put a period at the end' executes), interim results are never assessed, identical text is not assessed twice, rejected commands preserve state, typed submit skips the detector, and queued work never interleaves.",
      },
      {
        path: "js/tests/note-command-panel.test.js",
        count: 7,
        proves:
          "The DOM binding: the command box is separate from the note, Run executes typed text without the detector, Clear empties the command without touching the note, listener errors are reported.",
      },
    ],
    untested: [
      "First-sentence speech before the terminal event.",
      "Ordered sentence playback and terminal-tail flushing.",
      "Cancellation of agent transport, prepared audio, active playback, and late events.",
      "Two coordinators sharing one microphone.",
    ],
    next: [
      "Write the failing contract suite for first-sentence speech, ordered later sentences, terminal-tail flushing, and generation cancellation.",
      "Write the failing transport tests for fragmented NDJSON, malformed records, cumulative-message normalization, and aborting the child process.",
    ],
  },
  diagrams: [
    {
      title: "Designed first-sentence path",
      caption:
        "The coordinator can release sentence one while Toyota is still generating sentence two. Speech preparation and later text generation overlap, while VoiceSession remains the authoritative generation fence.",
      code: `sequenceDiagram
  participant UI
  participant CC as ConversationCoordinator
  participant VS as VoiceSession
  participant Agent as ConversationAgent
  participant Seg as SentenceSegmenter
  participant SQ as SpeechQueue

  UI->>CC: start turn with speech enabled
  CC->>VS: beginTurn
  VS-->>CC: generation 7
  CC->>Agent: submit turn and generation 7
  Agent-->>CC: assistant text delta with sentence 1
  CC->>Seg: push delta
  Seg-->>CC: complete sentence 1
  CC->>SQ: enqueue sentence 1
  SQ-->>UI: speech starts
  Agent-->>CC: assistant text delta with sentence 2
  CC->>SQ: enqueue sentence 2
  Agent-->>CC: terminal
  CC->>SQ: finish generation 7
  SQ-->>CC: playback drained
  CC->>VS: completeTurn generation 7`,
    },
    {
      title: "Where the coordinator sits",
      caption:
        "Everything the channel touches is an injected contract. The concrete HTTP adapters are supplied at the composition root and can be swapped for local implementations without editing the channel.",
      code: `flowchart TB
  Panel["NoteCommandPanelRenderer<br/>(DOM only)"]
  Listener["ContinuousListener"]
  VCC["VoiceCommandChannel<br/>(policy — no DOM, no HTTP)"]
  Buf[TranscriptBuffer]
  CD{{"CompletenessDetector<br/>port"}}
  CI{{"CommandInterpreter<br/>port"}}
  ND{{"NoteDocument<br/>port"}}
  HCD[HttpCompletenessDetector]
  HCI[HttpNoteCommandInterpreter]
  Surf["ReadOnlyNoteSurface<br/>+ TranscriptSyncedNote"]

  Listener -->|"onResult"| Panel
  Panel --> VCC
  VCC --> Buf
  VCC --> CD
  VCC --> CI
  VCC --> ND
  CD -.implemented by.-> HCD
  CI -.implemented by.-> HCI
  ND -.implemented by.-> Surf`,
    },
    {
      title: "Serialised queue under overlapping speech",
      caption:
        "Both fragments arrive before any work resolves. The queue guarantees ordering; it does not yet guarantee the first result is still wanted — that needs VoiceSession.",
      code: `sequenceDiagram
  participant CL as ContinuousListener
  participant VCC as VoiceCommandChannel
  participant CI as CommandInterpreter

  CL->>VCC: handleSpeech("first", final)
  CL->>VCC: handleSpeech("second", final)
  VCC->>CI: apply(note, "first")
  Note over VCC,CI: second fragment waits —<br/>no interleaving
  CI-->>VCC: outcome
  VCC->>CI: apply(note, "first second")
  CI-->>VCC: outcome`,
    },
  ],
  nextWork: [
    "Add failing tests under js/abstract/conversation_coordinator/tests before implementing runtime behavior.",
    "Implement a deterministic SentenceSegmenter Strategy and ordered SpeechQueue behind their typed ports.",
    "Implement StreamingLettaAgentAdapter over a validated NDJSON endpoint backed by the CLI's stream-json output.",
    "Adopt the coordinator in Toyota's InputOptionsRenderer, then add microphone speech-start barge-in.",
  ],
};
