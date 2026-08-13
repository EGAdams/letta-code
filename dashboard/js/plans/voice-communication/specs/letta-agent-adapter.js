import { Status } from "../../interface-spec.js";

export const lettaAgentAdapterSpec = {
  id: "letta-agent-adapter",
  name: "LettaAgentAdapter",
  group: "Planned core",
  tagline:
    "Partially real: LettaClient isolates the HTTP, but there is no conversation adapter and no streaming.",
  status: Status.PARTIAL,
  statusNote:
    "Transport adapter exists and is used by five strategies. The conversation-shaped adapter does not.",
  responsibility: [
    "Translate the Letta API into whatever contract the application actually needs, so no policy object ever learns Letta's URL shapes, payload keys, or response envelope.",
    "Today one small piece of this is real and load-bearing: LettaClient wraps urllib with three methods, and every Letta-backed strategy in the voice system goes through it. Swapping the transport (or faking it in tests) is a one-object change, and all five strategies' tests do exactly that.",
    "What is missing is the conversation-shaped adapter: translating a Letta message stream into typed assistant events with a generation identity, and cancelling a run. LettaClient only knows request/response.",
  ],
  contract: {
    language: "python",
    code: `LettaClient   voice/letta_client.py   (shipped, 3 methods)

  clear_messages(agent_id)        reset history; failure never blocks the call
  send_message(agent_id, text)    POST /v1/agents/{id}/messages, stream=False
  resolve_agent_id(name)          GET /v1/agents?limit=200

LettaAgentAdapter   (proposed — not implemented)

  submit(turn, generationId)  -> stream of typed AgentEvent
  cancel(generationId)        -> void`,
    note: "send_message hardcodes stream:false. Letta v0.16.7 on this server has streaming and background mode broken, which is why — but the limitation is currently invisible to callers.",
  },
  implementations: [
    {
      name: "LettaClient",
      kind: "current",
      file: "voice/letta_client.py",
      note: "The transport adapter. Used by cleanup, receptionist, router, completeness and interpreter strategies.",
    },
    {
      name: "LettaAgentCleanup",
      kind: "current",
      file: "voice/cleanup.py",
      note: "Use-case adapter: transcript → tidied text.",
    },
    {
      name: "LettaReceptionistIntentStrategy",
      kind: "current",
      file: "voice/receptionist.py",
      note: "Use-case adapter: transcript → {addressed, cleaned_text}.",
    },
    {
      name: "LettaAgentRouteStrategy",
      kind: "current",
      file: "router/classify.py",
      note: "Use-case adapter: transcript → {agent, remainder}, with a deterministic first tier.",
    },
    {
      name: "LettaCommandCompletenessStrategy",
      kind: "current",
      file: "voice/note_completeness.py",
      note: "Use-case adapter: partial command → {complete, reason}.",
    },
    {
      name: "LettaNoteCommandInterpreter",
      kind: "current",
      file: "voice/note_interpreter.py",
      note: "Use-case adapter: note + command → typed intent.",
    },
    {
      name: "LettaAgentAdapter",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "The streaming, cancellable conversation adapter. Not started.",
    },
  ],
  dependencies: {
    usedBy: [
      "All five Letta-backed strategies in voice/ and router/",
      "IConversationAgent (planned) — would be its first adapter",
    ],
    dependsOn: ["Letta HTTP API", "urllib (stdlib)"],
    note: "Correct direction: the strategies depend on LettaClient's three methods, and every strategy's tests inject a fake client with the same three methods. No strategy imports urllib.",
  },
  developmentStatus: {
    done: [
      "One transport adapter isolates all Letta HTTP access for the voice system.",
      "Five use-case adapters share one pattern: clear history, one strict-JSON prompt, strict parse, fail closed.",
      "Agent-id resolution is centralised, and the note-command factory now degrades to a fail-closed service when Letta is unreachable instead of raising into the request handler.",
      "Every adapter is tested with an injected fake client — no test touches the network.",
    ],
    gaps: [
      "No streaming: send_message pins stream:false, so a long reply arrives as one lump.",
      "No cancellation — a Letta call runs to completion or times out.",
      "No generation identity on any call, so a late reply cannot be fenced.",
      "resolve_agent_id fetches up to 200 agents and scans linearly on every cold build.",
      "BLOCKED: the default agent for cleanup/receptionist/note-commands runs on lc-gemini, which now returns 401 UNAUTHENTICATED. Every one of these adapters is currently failing closed in production.",
    ],
  },
  tests: {
    files: [
      {
        path: "dashboard/tests/test_cleanup.py",
        count: 7,
        proves:
          "Prompt construction, history clearing, and that a failed cleanup falls back to the raw transcript rather than losing it.",
      },
      {
        path: "dashboard/tests/test_router_classify.py",
        count: 14,
        proves:
          "The deterministic exact-name tier runs before any LLM call, word-boundary matching, and that every parse failure fails closed to 'no agent'.",
      },
      {
        path: "dashboard/tests/test_note_commands.py",
        count: 27,
        proves:
          "Both newer adapters, including that an unreachable Letta yields a fail-closed service instead of an exception, and that a down server is never cached.",
      },
      {
        path: "dashboard/tests/test_receptionist.py",
        count: 5,
        proves:
          "Strict JSON parsing and refusal to act on invented model output.",
      },
    ],
    untested: [
      "LettaClient itself has no direct unit test — it is only exercised through fakes that replace it.",
      "resolve_agent_id's pagination behaviour when more than 200 agents exist.",
      "A 401 from the provider (the failure actually happening in production right now) is covered only by the generic 'exception → fail closed' path.",
    ],
    next: [
      "A LettaClient test against a stubbed urlopen, pinning URL shapes and the clear_messages-never-raises guarantee.",
      "A test asserting a provider auth failure produces a distinguishable status, so the dashboard can show 'LLM auth failed' instead of silently waiting.",
    ],
  },
  diagrams: [
    {
      title: "Adapter layering as it exists",
      caption:
        "Five use-case adapters, one transport adapter, one external system. Tests replace LettaClient wholesale.",
      code: `flowchart TB
  subgraph Policy["Application policy"]
    P1[VoicePipeline]
    P2[NoteCommandService]
    P3["Router endpoint"]
    P4["Receptionist endpoint"]
  end
  subgraph Ports["Ports (ABCs)"]
    C1{{CleanupStrategy}}
    C2{{CommandCompletenessStrategy}}
    C3{{NoteCommandInterpreter}}
    C4{{RouteStrategy}}
    C5{{ReceptionistIntentStrategy}}
  end
  subgraph Adapters["Letta use-case adapters"]
    A1[LettaAgentCleanup]
    A2[LettaCommandCompletenessStrategy]
    A3[LettaNoteCommandInterpreter]
    A4[LettaAgentRouteStrategy]
    A5[LettaReceptionistIntentStrategy]
  end
  LC["LettaClient<br/>(transport adapter)"]
  Letta[(Letta HTTP API)]

  P1 --> C1
  P2 --> C2
  P2 --> C3
  P3 --> C4
  P4 --> C5
  A1 -.-> C1
  A2 -.-> C2
  A3 -.-> C3
  A4 -.-> C4
  A5 -.-> C5
  A1 --> LC
  A2 --> LC
  A3 --> LC
  A4 --> LC
  A5 --> LC
  LC --> Letta`,
    },
    {
      title: "One adapter call, including the current failure",
      caption:
        "The 401 is real and happening now: the shared worker agent sits on a dead Gemini BYOK handle, so every adapter returns its fail-closed value and the UI simply looks idle.",
      code: `sequenceDiagram
  participant S as LettaCommandCompletenessStrategy
  participant LC as LettaClient
  participant Letta
  participant Gemini as lc-gemini provider

  S->>LC: clear_messages(agent)
  LC->>Letta: POST .../messages/clear
  S->>LC: send_message(agent, prompt)
  LC->>Letta: POST /v1/agents/{id}/messages
  Letta->>Gemini: generate
  rect rgb(247,235,233)
    Gemini--xLetta: 401 UNAUTHENTICATED
    Letta--xLC: HTTP 401 llm_authentication
  end
  LC--xS: raises
  S-->>S: CommandCompleteness.incomplete("detector unavailable")
  Note over S: fails closed — correct,<br/>but invisible to the user`,
    },
  ],
  nextWork: [
    "Repoint transcript-cleanup-agent to chatgpt-plus-pro/gpt-5.4-mini and re-run the live check. This unblocks three shipped features.",
    "Surface provider auth failures distinctly from 'still thinking', so a dead LLM is visible in the dashboard rather than looking like silence.",
    "Add a direct LettaClient test with a stubbed urlopen.",
    "Once IConversationAgent exists, build LettaAgentAdapter against it — streaming first, cancellation second.",
  ],
};
