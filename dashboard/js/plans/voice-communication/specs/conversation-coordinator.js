import { Status } from "../../interface-spec.js";

export const conversationCoordinatorSpec = {
  id: "conversation-coordinator",
  name: "ConversationCoordinator",
  group: "Planned core",
  tagline:
    "Typed Mediator for streamed agent text, sentence-level speech, and interruption.",
  status: Status.PARTIAL,
  statusNote:
    "Toyota now uses the typed coordinator, streaming NDJSON Letta adapter, deterministic sentence segmentation, and ordered cancellable speech queue.",
  responsibility: [
    "Coordinate one finalized user turn into exactly one agent run, and make sure overlapping speech never produces overlapping responses. It is the Mediator between capture, the agent, and output.",
    "The shipped VoiceCommandChannel already owns a meaningful piece of this: it serialises work onto a promise chain, dedupes identical finalized transcripts, and decides when an instruction is complete enough to act on. That last decision — completeness judged from accumulated text rather than a silence timer — is the part worth keeping in any rebuild.",
    "The typed coordinator defines dialogue coordination without DOM, HTTP, Letta, or audio-provider dependencies. Input Options delegates its turn lifecycle to this Mediator; Toyota injects the streaming adapter while other agents retain the batch adapter during the pilot.",
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
      kind: "current",
      file: "js/abstract/conversation_coordinator/src/conversation-coordinator.ts",
      note: "Typed Mediator implementation for agent events, generation fencing, sentence segmentation, ordered speech, observers, and interruption.",
    },
    {
      name: "StreamingLettaAgentAdapter",
      kind: "current",
      file: "js/implementation/conversation_stream_agent/src/streaming-letta-agent-adapter.ts",
      note: "Maps validated NDJSON provider records into assistant deltas and propagates browser cancellation through AbortController.",
    },
    {
      name: "SequentialSpeechQueue",
      kind: "current",
      file: "js/implementation/conversation_coordinator/src/sequential-speech-queue.ts",
      note: "Keeps sentence playback ordered and registers cancellation ownership with VoiceSession.",
    },
  ],
  dependencies: {
    usedBy: [
      "InputOptionsRenderer",
      "Toyota receptionist streaming pilot",
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
      "Toyota's response text now renders incrementally and complete sentences enter TTS before the terminal result.",
      "The Pydantic NDJSON endpoint validates requests and outgoing envelopes without adding behavior to server.py.",
      "AbortController cancellation closes the HTTP stream; the generator then kills and reaps the CLI process group.",
      "Work is serialised on a promise chain, so an in-flight edit cannot interleave with the next speech fragment.",
      "Identical finalized text is never assessed twice — important because the recognizer re-flushes its tail on every silence restart.",
      "Completeness is judged from accumulated text via an injected detector, never from a silence timeout.",
      "A rejected command leaves both the note and the command text alone, so the user can reword and retry.",
      "Errors from either collaborator surface as status without wedging the queue.",
    ],
    gaps: [
      "Streaming is piloted on Toyota; other Input Options agents still use the batch adapter.",
      "Edge TTS still synthesizes one sentence per HTTP request, so later work can add audio preparation overlap if sentence gaps remain audible.",
      "Chat retains its existing turn closure and batch /api/test adapter.",
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
      {
        path: "js/abstract/conversation_coordinator/tests/conversation-coordinator.test.ts",
        count: 5,
        proves:
          "Split sentence boundaries, abbreviation and decimal handling, maximum phrase latency, first-sentence speech before terminal, and stale generation cancellation.",
      },
      {
        path: "js/implementation/conversation_stream_agent/tests/streaming-letta-agent-adapter.test.ts",
        count: 3,
        proves:
          "Fragmented NDJSON parsing, malformed record rejection, conversation resume persistence, and request abort.",
      },
      {
        path: "js/implementation/conversation_coordinator/tests/sequential-speech-queue.test.ts",
        count: 2,
        proves:
          "Sentence playback remains ordered and cancellation prevents queued late speech.",
      },
    ],
    untested: [
      "Two coordinators sharing one microphone.",
      "Measured first-audio latency over the live Tailscale browser path.",
    ],
    next: [
      "Measure Toyota's time to first text and first audio over the live secure URL.",
      "If sentence gaps are audible, add a speech preparation port so sentence N+1 can synthesize while sentence N is playing.",
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
    "Measure Toyota's time to first text and first audio through the secure browser URL.",
    "Add optional concurrent TTS preparation if sentence-to-sentence gaps remain visible in that trace.",
    "After the pilot is stable, select the streaming adapter for other Input Options agents.",
  ],
};
