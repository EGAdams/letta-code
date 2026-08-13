import { Status } from "../../interface-spec.js";

export const overviewSpec = {
  id: "overview",
  name: "Overview",
  group: "Start here",
  tagline:
    "What the voice system is, what actually shipped, and what is still only a plan.",
  status: Status.PARTIAL,
  statusNote:
    "A working voice stack ships inside the dashboard. The Pipecat rebuild described in the original plan has not been started.",
  links: [
    {
      label: "Original plan document (v1, verbatim)",
      href: "/voice_communication_plan_v1.html",
    },
  ],
  responsibility: [
    "Voice Communication is the path from a spoken sentence to a Letta agent doing something about it, and back to speech. Today that path is: browser captures audio → text arrives (whisper.cpp for push-to-talk, browser SpeechRecognition for continuous listening) → a narrow Letta-backed strategy decides what the text means → an agent acts → edge-tts speaks the reply.",
    "The single most important thing to understand before working here: there are TWO architectures in play. The original plan (2026-08-01) designed a Pipecat-based system in /home/adamsl/talking_agent_parts around VoiceSession, ConversationCoordinator, IConversationAgent and LettaAgentAdapter. That directory still contains only the plan document — none of those objects exist. Meanwhile a different, working voice system grew inside dashboard/, and its seams turned out narrower and differently named.",
    "This workspace documents the code that exists, marks the planned objects honestly as Planned, and shows where the two designs meet. Where the shipped code has a real seam the plan never named, it gets a tab. Where the plan named an object nobody built, it gets a tab that says so and explains what stands in for it today.",
  ],
  contract: {
    language: "text",
    code: `Shipped ports (all have an ABC/base class + at least one implementation + tests)

  Python  dashboard/voice/, dashboard/router/
    TranscriptionStrategy        audio bytes  -> raw text
    CleanupStrategy              raw text     -> tidied text
    SpeechSynthesisStrategy      text         -> audio bytes
    ReceptionistIntentStrategy   transcript   -> {addressed, cleaned_text}
    RouteStrategy                transcript   -> {agent, remainder}
    CommandCompletenessStrategy  partial cmd  -> {complete, reason}
    NoteCommandInterpreter       note + cmd   -> edit | save | none
    NoteRepository               note         -> SavedNote

  Browser  dashboard/js/abstract/
    ContinuousListener           streaming speech (State)
    VoiceRecorder                push-to-talk capture (State)
    SpeechSynthesizer            speaking replies
    NoteDocument                 the text surface being edited
    TranscriptBuffer             final/interim accumulation
    VoiceCommandChannel          the one real coordinator

Planned, not built (talking_agent_parts/ contains only the plan document)

    VoiceSession  ConversationCoordinator  IConversationAgent
    LettaAgentAdapter  SpokenOutputPolicy  PipelineFactory
    ISessionObserver  IClock/IIdSource  VoiceCommunicationApplication`,
    note: "Every Letta-backed strategy above follows the same shape: clear the agent's history, send one strict-JSON prompt, parse it strictly, and fail closed on anything unexpected.",
  },
  implementations: [
    {
      name: "Dashboard voice stack",
      kind: "current",
      file: "dashboard/voice/, dashboard/router/, dashboard/js/",
      note: "The system that actually runs. 8 Python ports + 6 browser ports, ~180 tests.",
    },
    {
      name: "Pipecat rebuild",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "Plan document only. Phase 0 (baseline, ADR-001, pyproject) never started.",
    },
    {
      name: "voice_agent prototype",
      kind: "deprecated",
      file: "/home/adamsl/voice_agent/",
      note: "Standalone CLI prototype. Kept as evidence + recordings; the plan explicitly says do not port VoiceAgent or LanguageProcessor.",
    },
  ],
  dependencies: {
    usedBy: [
      "Dashboard home screen — Toyota's note + command channel",
      "Dashboard Agents home — speech routing to a named agent",
      "Every agent's Input Options page — push-to-talk and spoken replies",
    ],
    dependsOn: [
      "Letta HTTP API (via voice/letta_client.py — the one transport adapter)",
      "whisper.cpp + ffmpeg binaries (borrowed from lettabot)",
      "edge-tts (server-side speech synthesis)",
      "Browser SpeechRecognition + MediaRecorder APIs",
    ],
    note: "The layering mostly holds: policy talks to ports, and concrete technology sits behind adapters. The two places it leaks are documented on the ConversationCoordinator and IConversationAgent tabs — renderers still POST to /api/letta-code-message directly instead of going through a conversation port.",
  },
  developmentStatus: {
    done: [
      "Capture works on both paths: push-to-talk (MediaRecorder → whisper.cpp) and continuous (browser SpeechRecognition), each behind its own State-machine port.",
      "Speech-to-agent routing works and fails closed — an ambiguous transcript never guesses an agent.",
      "The note + command channel is complete end-to-end, including LLM-judged command completeness and agent-chosen save filenames.",
      "Speech synthesis works server-side (edge-tts) with a per-agent voice catalog.",
      "Every port has an ABC/base class, at least one implementation, and unit tests with injected collaborators.",
    ],
    gaps: [
      "There is no session object. Nothing owns 'one conversation' — state is split across ListenerState, RecorderState and per-render closures.",
      "There is no generation fencing, so a late reply from a superseded turn cannot be discarded. Barge-in/interruption is impossible today.",
      "There is no IConversationAgent port. Renderers call POST /api/letta-code-message directly, so a non-Letta conversation engine cannot be substituted.",
      "Nothing is cancellable. Every Letta call runs to completion or times out.",
      "The Letta adapter is request/response only — no streaming, so replies arrive in one lump after up to 900 seconds.",
      "BLOCKER: the transcript-cleanup-agent runs on lc-gemini, which now returns 401. Voice cleanup, the receptionist intent policy and the note-command channel all default to that agent and are failing closed right now.",
    ],
  },
  tests: {
    files: [
      {
        path: "dashboard/tests/ (voice + router)",
        count: 68,
        proves:
          "Transcription arg-building, cleanup fallback, synthesis caching, routing fail-closed behaviour, receptionist intent parsing, and the whole note-command channel.",
      },
      {
        path: "dashboard/js/tests/ (voice-related)",
        count: 111,
        proves:
          "Both capture state machines, speech synthesis selection, transcript merging, the command channel's completeness gating, and the note surfaces.",
      },
    ],
    untested: [
      "Nothing tests two speech paths running at once — the note listener and the command listener both hold a browser SpeechRecognition instance.",
      "No test covers a Letta call that hangs rather than fails; every failure test raises immediately.",
      "No end-to-end test drives audio in and asserts speech out.",
    ],
    next: [
      "A characterization test for the current /api/letta-code-message call path, so an IConversationAgent port can be introduced without changing behaviour.",
      "A latency measurement harness: end-of-speech → transcript, and transcript → first audio.",
    ],
  },
  diagrams: [
    {
      title: "What actually runs today",
      caption:
        "Solid boxes exist and are tested. The dashed box is the gap: no session or conversation port sits between the UI and Letta, so renderers reach the agent directly.",
      code: `flowchart TB
  subgraph Browser
    Mic([Microphone])
    CL["ContinuousListener<br/>(State)"]
    VR["VoiceRecorder<br/>(State)"]
    TB[TranscriptBuffer]
    VCC["VoiceCommandChannel<br/>the only coordinator"]
    ND["NoteDocument"]
    SS["SpeechSynthesizer"]
  end
  subgraph Server["dashboard/ Python"]
    TR["TranscriptionStrategy<br/>whisper.cpp"]
    CU[CleanupStrategy]
    RS[RouteStrategy]
    RI[ReceptionistIntentStrategy]
    CC[CommandCompletenessStrategy]
    NI[NoteCommandInterpreter]
    NR[NoteRepository]
    TTS["SpeechSynthesisStrategy<br/>edge-tts"]
    LC["LettaClient<br/>(Adapter)"]
  end
  Letta[(Letta agents)]

  Mic --> CL
  Mic --> VR
  VR -->|"POST /api/voice"| TR
  TR --> CU
  CU --> LC
  CL --> TB
  TB --> VCC
  VCC -->|"POST /api/note-command-complete"| CC
  VCC -->|"POST /api/note-command-apply"| NI
  NI --> NR
  VCC --> ND
  CL --> RS
  CL --> RI
  CC --> LC
  NI --> LC
  RS --> LC
  RI --> LC
  LC --> Letta
  TTS --> SS

  MISSING["MISSING: VoiceSession +<br/>IConversationAgent<br/>renderers POST Letta directly"]
  ND -.-> MISSING
  MISSING -.-> Letta

  style MISSING stroke-dasharray: 6 4,stroke:#9b2c39,color:#9b2c39`,
    },
    {
      title: "Plan vs. reality",
      caption:
        "The plan's objects on the left, what stands in for each today on the right. Four of the plan's six headline objects have no code at all.",
      code: `flowchart LR
  subgraph Planned["Plan (talking_agent_parts) — 0 lines written"]
    VS[VoiceSession]
    CO[ConversationCoordinator]
    ICA[IConversationAgent]
    LAA[LettaAgentAdapter]
  end
  subgraph Shipped["Shipped (dashboard/)"]
    LS["ListenerState + RecorderState<br/>no session object"]
    VCC["VoiceCommandChannel<br/>note commands only"]
    STRAT["4 narrow Letta strategies<br/>no single port"]
    LC["LettaClient<br/>3 methods, no streaming"]
  end
  VS -.->|"stands in"| LS
  CO -.->|"partially"| VCC
  ICA -.->|"scattered across"| STRAT
  LAA -.->|"partially"| LC`,
    },
    {
      title: "One turn, end to end (note dictation + a spoken command)",
      caption:
        "The completeness check is the reason a pause mid-sentence does not fire a half-command. Note that no object here owns the turn — that is the missing VoiceSession.",
      code: `sequenceDiagram
  actor EG
  participant CL as ContinuousListener
  participant TB as TranscriptBuffer
  participant VCC as VoiceCommandChannel
  participant CC as CommandCompletenessStrategy
  participant NI as NoteCommandInterpreter
  participant ND as NoteDocument

  EG->>CL: "Put a"
  CL->>TB: accept(text, final)
  TB->>VCC: committed = "Put a"
  VCC->>CC: assess("Put a")
  CC-->>VCC: complete=false, "trails off"
  Note over VCC,ND: four second pause — nothing happens,<br/>because no timer drives this
  EG->>CL: "period at the end"
  CL->>TB: accept(text, final)
  TB->>VCC: committed = "Put a period at the end"
  VCC->>CC: assess(...)
  CC-->>VCC: complete=true
  VCC->>NI: apply(note, command)
  NI-->>VCC: kind=edit, revised note
  VCC->>ND: setText(revised)`,
    },
  ],
  nextWork: [
    "Unblock the LLM: repoint transcript-cleanup-agent off the dead lc-gemini handle onto chatgpt-plus-pro/gpt-5.4-mini. Three shipped features are failing closed until this is done.",
    "Build VoiceSession — the smallest object that owns one conversation's identity, state and current generation. Everything else on this page is blocked behind it.",
    "Extract IConversationAgent from the direct /api/letta-code-message calls, with the existing Letta path as its first adapter.",
    "Decide, explicitly, whether the Pipecat rebuild is still the direction or whether the shipped dashboard stack is now the system. Right now the plan and the code disagree, and that ambiguity is itself a risk.",
  ],
};
