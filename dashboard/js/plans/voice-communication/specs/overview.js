import { Status } from "../../interface-spec.js";

export const overviewSpec = {
  id: "overview",
  name: "Overview",
  group: "Start here",
  tagline:
    "What the voice system is, what actually shipped, and what is still only a plan.",
  status: Status.PARTIAL,
  statusNote:
    "The dashboard voice stack is the production foundation. Input Options and Chat use the ConversationAgent port, session fencing, and speech policy. The media boundary is next; Pipecat will be integrated there in later slices.",
  links: [
    {
      label: "Current integration decision and delivery order",
      href: "/voice_communication/docs/the_sunday_plan.md",
    },
    {
      label: "Original plan document (v1, verbatim)",
      href: "/voice_communication_plan_v1.html",
    },
  ],
  responsibility: [
    "Voice Communication is the path from a spoken sentence to a Letta agent doing something about it, and back to speech. Today that path is: browser captures audio → text arrives (whisper.cpp for push-to-talk, browser SpeechRecognition for continuous listening) → a narrow Letta-backed strategy decides what the text means → an agent acts → edge-tts speaks the reply.",
    "The original plan (2026-08-01) designed a standalone Pipecat system in /home/adamsl/talking_agent_parts. A working voice system grew inside dashboard/ with narrower, tested seams. EG chose the dashboard as the production foundation on 2026-09-20; Pipecat is a future adapter for media capabilities the dashboard needs.",
    "The browser-side VoiceSession, ConversationAgent port, and SpokenOutputPolicy are built and tested. Input Options uses LettaAgentAdapter; Chat uses the typed TestChatAgentAdapter for its distinct reply shape. Both renderers fence stale turns and own cancellable speech playback.",
    "This workspace documents the code that exists, marks each object honestly, and shows where the two designs meet. Where the shipped code has a real seam the plan never named, it gets a tab. Where the plan named an object nobody built, it gets a tab that says so and explains what stands in for it today.",
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

Built from the plan, browser side (the conversation port has one live caller)

  Browser  dashboard/js/
    VoiceSession                 lifecycle + generation fencing
    Clock / IdSource             injected time and identity
    ConversationAgent            submit(turn, gen) -> AgentEvent stream
    LettaAgentAdapter            the first adapter, over the live endpoint
    FakeConversationAgent        the second, for tests and offline UI
    SpokenOutputPolicy           the one gate in front of the speaker

Still only a plan

    ConversationCoordinator  PipelineFactory
    VoiceCommunicationApplication`,
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
      name: "Pipecat media integration",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "Planned incremental adapter behind the dashboard's media ports; no live Pipecat implementation yet.",
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
    note: "Input Options and Chat send through ConversationAgent adapters and use VoiceSession plus SpokenOutputPolicy. The Agents-home router only classifies and hands text to Input Options.",
  },
  developmentStatus: {
    done: [
      "Capture works on both paths: push-to-talk (MediaRecorder → whisper.cpp) and continuous (browser SpeechRecognition), each behind its own State-machine port.",
      "Speech-to-agent routing works and fails closed — an ambiguous transcript never guesses an agent.",
      "The note + command channel is complete end-to-end, including LLM-judged command completeness and agent-chosen save filenames.",
      "Speech synthesis works server-side (edge-tts) with a per-agent voice catalog.",
      "Every port has an ABC/base class, at least one implementation, and unit tests with injected collaborators.",
      "The shared worker agent (transcript-cleanup-agent) runs on chatgpt-plus-pro/gpt-5.6-luna as of 2026-08-13, replacing the dead lc-gemini handle that had been silently failing every voice-cleanup, receptionist and note-command call. Verified live end to end.",
      "InputOptionsRenderer now uses an injected ConversationAgent; its renderer test runs with FakeConversationAgent and proves reasoning and tool events stay out of the visible and spoken reply.",
      "This guide is the shipped documentation: 14 tabs served at Project Plans → Voice Communication, navigated from the dashboard's own sub-nav, with the interface list driven by the same specs that render each page so the tabs cannot drift from the content.",
    ],
    gaps: [
      "The existing /api/voice media contract still needs tests before a Pipecat adapter can share it.",
      "Automatic microphone echo detection is unverified; recognized speaker echo can interrupt the current answer.",
      "Cancellation is delivery-side only — the endpoint has no server-side cancel, so a cancelled Letta call still runs to completion.",
      "The Letta adapter is request/response only — no streaming, so replies arrive in one lump after up to 1770 seconds.",
      "Every finalized speech fragment costs one 3-6s LLM round-trip to the completeness detector. That, not model choice, is the dominant latency in the loop — see the Note Command Channel tab.",
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
      "A renderer-level test that a reply arriving after an interrupt is never spoken — the same assertion as the VoiceSession unit test, one layer up, and the proof that adoption worked.",
      "A latency measurement harness: end-of-speech → transcript, and transcript → first audio.",
    ],
  },
  diagrams: [
    {
      title: "The adoption backlog, in order",
      caption:
        "Step 1 is now wired in InputOptionsRenderer. The remaining order is session and speech gating, interruption, then the other renderer paths.",
      code: `flowchart LR
  subgraph Live["Live renderers — do this work here"]
    IOR["InputOptionsRenderer.send()<br/>ConversationAgent port"]
    ARR["AgentsRouterRenderer"]
    CDR["ChatDetailRenderer<br/>POST /api/test"]
    VCC["VoiceCommandChannel"]
  end
  subgraph Built["Built and tested ports"]
    VS["VoiceSession<br/>the fence"]
    ICA{{"ConversationAgent<br/>port"}}
    LAA["LettaAgentAdapter"]
    SOP["SpokenOutputPolicy"]
    NEW["second adapter<br/>NOT YET WRITTEN"]
  end
  TTS["SpeechSynthesizer"]

  IOR -->|"1"| LAA
  IOR -->|"2"| VS
  IOR -->|"2"| SOP
  ARR -->|"4"| LAA
  CDR -->|"4"| NEW
  VCC -->|"5"| VS
  LAA -.satisfies.-> ICA
  NEW -.satisfies.-> ICA
  SOP --> TTS
  VS -.->|"accepts(gen)"| SOP`,
    },
    {
      title: "What actually runs today",
      caption:
        "The Python capture and speech paths run. Input Options also uses ConversationAgent now; VoiceSession and SpokenOutputPolicy are the remaining live renderer boundary.",
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

  MISSING["NEXT: VoiceSession +<br/>SpokenOutputPolicy<br/>for Input Options"]
  ND -.-> MISSING
  MISSING -.-> Letta

  style MISSING stroke-dasharray: 6 4,stroke:#9b2c39,color:#9b2c39`,
    },
    {
      title: "Original plan and current dashboard",
      caption:
        "The core browser objects were built in dashboard/js. Input Options uses the agent port; session and speech gating are the next adoption step. Pipecat remains a future media adapter.",
      code: `flowchart LR
  subgraph Original["Original proposal"]
    PIC["Pipecat runtime"]
    CO[ConversationCoordinator]
  end
  subgraph Shipped["Shipped (dashboard/)"]
    MEDIA["MediaRecorder + Whisper<br/>edge-tts"]
    IO[InputOptionsRenderer]
    PORT{{ConversationAgent}}
    LETTA[LettaAgentAdapter]
    VS["VoiceSession<br/>built, unused"]
    SOP["SpokenOutputPolicy<br/>built, unused"]
  end
  IO --> PORT
  LETTA -.satisfies.-> PORT
  MEDIA --> IO
  PIC -.->|"future media adapter"| MEDIA
  CO -.->|"future coordinator"| VS
  VS -.-> SOP`,
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
  gotchas: [
    {
      title:
        "The reply paths are fenced; the media path needs characterization.",
      body: "Input Options and Chat use VoiceSession and SpokenOutputPolicy. The current /api/voice upload and browser microphone lifecycle still need contract tests before a Pipecat adapter can implement the same boundary.",
    },
    {
      title: "The two reply paths have different HTTP shapes.",
      body: "InputOptionsRenderer uses /api/letta-code-message, which returns { ok, reply }. ChatDetailRenderer uses /api/test, which returns { replies: [{type, text}] }; its typed TestChatAgentAdapter maps those rows to events. AgentsRouterRenderer only calls /api/route-detect and hands text to Input Options.",
    },
    {
      title: "Cancellation here means 'do not deliver', not 'stop working'.",
      body: "/api/letta-code-message has no server-side cancel. LettaAgentAdapter.cancel() suppresses the result and nothing more — the Letta run continues to completion and still costs its tokens and its 1770 seconds. That is a real guarantee and a useful one, but do not build a UI that promises the user it stopped the agent.",
    },
    {
      title: "Adoption moves state; it does not just add a constructor call.",
      body: "Conversation state today lives in closures inside render() functions — the conversation id, the in-flight flag, what has been spoken. A session that is constructed alongside that state instead of taking ownership of it gives you two sources of truth and a fence that disagrees with the UI. When you adopt VoiceSession in a renderer, delete the closure state it replaces in the same edit.",
    },
    {
      title: "A renderer is rebuilt on every open; the listener is not.",
      body: "js/boot/agent-detail-renderers.js constructs a fresh renderer each time a tab is opened, but routerListener is deliberately long-lived so listening survives the hand-off between pages. Decide consciously which side of that line the session sits on. A session rebuilt per render cannot fence a reply that outlives the tab — which is exactly the case worth fencing.",
    },
  ],
  nextWork: [
    "1–2 · DONE: Input Options and Chat use ConversationAgent, VoiceSession, and SpokenOutputPolicy. Late replies are silent in renderer tests; real agent sends have not been exercised in this slice.",
    "3 · IN PROGRESS: a new recognized utterance interrupts Toyota's active answer. Verify barge-in with a real microphone and check for speaker echo before claiming acoustic interruption is reliable.",
    "4 · DONE: ChatDetailRenderer uses typed TestChatAgentAdapter and SpokenOutputPolicy. AgentsRouterRenderer only routes text to Input Options and has no reply or speaker path. composeSpokenText was deleted.",
    "5 · Give VoiceCommandChannel a session and generation ids (js/abstract/voice-command-channel.js). It already serialises work, so it needs no new concurrency — it needs the fence, so a superseded command's result can be discarded rather than merely not started. See the ConversationCoordinator tab.",
    "6 · Only then consider ConversationCoordinator, the last unbuilt core object. It is the one place where waiting was right: with steps 1-5 done, its job is visible in real code rather than guessed at from the plan.",
    "Independent of all of the above — cut the completeness round-trip. A cheap local pre-filter that skips the LLM for obviously-incomplete fragments would remove most of the 3-6s wait per spoken pause. This is the single biggest user-visible win on this page and it touches none of the work above, so it can run in parallel.",
    "After adopting the live session and agent ports, characterize the current media contract. Add Pipecat as an adapter behind that contract, validate external events with Pydantic, and select it at the composition root. Keep the existing dashboard path available until parity is proven.",
  ],
};
