import { Status } from "../../interface-spec.js";

export const voiceSessionSpec = {
  id: "voice-session",
  name: "VoiceSession",
  group: "Planned core",
  tagline: "The object that would own one conversation. It does not exist yet.",
  status: Status.PLANNED,
  statusNote: "No code. The plan's first-slice object, never started.",
  responsibility: [
    "Own the identity and legal lifecycle of one voice conversation: which session this is, which agent turn ('generation') is currently live, and which state transitions are allowed — idle, listening, thinking, speaking, interrupted, closed.",
    "Its real job is generation fencing. When a user interrupts, the turn in flight becomes stale, and everything downstream needs one authoritative answer to 'is this output still wanted?'. Without that, a slow reply from an abandoned turn arrives late and gets spoken over the new one.",
    "It is deliberately framework-free: no Pipecat, no Letta, no browser APIs. That is what makes lifecycle rules testable without sleeps or a microphone.",
  ],
  contract: {
    language: "text",
    code: `VoiceSession   (proposed — not implemented)

  id                       -> SessionId          stable for the conversation
  state                    -> idle | listening | thinking | speaking
                              | interrupted | closed
  currentGeneration        -> GenerationId       the live agent turn

  beginTurn()              -> GenerationId       supersedes any live turn
  accepts(generationId)    -> bool               false once superseded
  interrupt()              -> void               current turn becomes stale
  close()                  -> void`,
    note: "Written from the plan's 'First object model' table, not from code — nothing implements this.",
  },
  implementations: [
    {
      name: "(none)",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "Directory contains only the plan document.",
    },
    {
      name: "ListenerState",
      kind: "current",
      file: "js/abstract/continuous-listener.interface.js",
      note: "Stands in partially: idle/listening only, per-listener, no generation and no session identity.",
    },
    {
      name: "RecorderState",
      kind: "current",
      file: "js/abstract/voice-recorder.interface.js",
      note: "Stands in partially: idle/recording/processing for one clip.",
    },
  ],
  dependencies: {
    usedBy: [
      "ConversationCoordinator (planned) — would consult it before releasing output",
      "SpokenOutputPolicy (planned) — would reject text from a superseded generation",
    ],
    dependsOn: [
      "IClock / IIdSource (planned) — injected so lifecycle tests need no sleeps or randomness",
    ],
    note: "Nothing concrete: that is the point. A session that imports Letta or a browser API cannot be tested without them.",
  },
  developmentStatus: {
    done: [
      "The contract is designed and recorded in the original plan.",
      "Two narrow state machines already exist and work (ListenerState, RecorderState) — evidence that the State pattern fits this codebase.",
    ],
    gaps: [
      "No VoiceSession class exists in any repository.",
      "No generation identity exists anywhere, so no stale output can be detected or discarded.",
      "Session state is currently spread across two listener state machines and closures inside render() functions, so nothing can answer 'what is this conversation doing right now?'.",
      "Interruption/barge-in is impossible to implement until this lands.",
    ],
  },
  tests: {
    files: [],
    untested: ["Every behaviour on this tab — there is no code and no test."],
    next: [
      "A failing test first: 'output from a superseded generation is rejected'. The plan names this as the first contract test, and it is the one that proves the object earns its keep.",
      "Transition-legality tests: speaking → interrupted is legal, closed → listening is not.",
    ],
  },
  diagrams: [
    {
      title: "Proposed lifecycle",
      caption:
        "The transition that matters is interrupted: it is what makes a live turn's output stale without tearing the session down.",
      code: `stateDiagram-v2
  [*] --> idle
  idle --> listening: start()
  listening --> thinking: turn finalized
  thinking --> speaking: first output token
  speaking --> listening: turn complete
  listening --> interrupted: user speaks over
  thinking --> interrupted: user speaks over
  speaking --> interrupted: user speaks over
  interrupted --> listening: new generation begins
  idle --> closed: close()
  listening --> closed: close()
  speaking --> closed: close()
  closed --> [*]
  note right of interrupted
    output carrying the old
    GenerationId is discarded
  end note`,
    },
    {
      title: "Why the gap hurts today",
      caption:
        "Without a session, a superseded reply has nothing to check itself against, so it is spoken anyway.",
      code: `sequenceDiagram
  actor EG
  participant UI as Renderer
  participant Letta
  participant TTS as SpeechSynthesizer

  EG->>UI: "what did we spend in March?"
  UI->>Letta: POST /api/letta-code-message
  EG->>UI: "no wait — April"
  UI->>Letta: POST /api/letta-code-message
  Letta-->>UI: answer for MARCH (slow)
  rect rgb(247,235,233)
    UI->>TTS: speak(March answer)
    Note over UI,TTS: nothing knows this turn<br/>was superseded
  end
  Letta-->>UI: answer for APRIL
  UI->>TTS: speak(April answer)`,
    },
  ],
  nextWork: [
    "Write the failing test: a session rejects output tagged with a superseded generation id.",
    "Implement VoiceSession with injected IClock/IIdSource so tests are deterministic.",
    "Give every outbound agent call a generation id, starting with the note-command channel's queue (which already serialises work and is the natural first caller).",
    "Only then wire interruption into ContinuousListener.",
  ],
};
