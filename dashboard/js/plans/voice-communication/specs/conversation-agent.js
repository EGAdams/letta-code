import { Status } from "../../interface-spec.js";

export const conversationAgentSpec = {
  id: "iconversationagent",
  name: "IConversationAgent",
  group: "Planned core",
  tagline:
    "The missing port. Renderers talk to Letta's HTTP endpoint directly, so no other engine can be substituted.",
  status: Status.PLANNED,
  statusNote:
    "Not implemented. Four narrow Letta strategies and one direct fetch stand in for it.",
  responsibility: [
    "Submit one user turn to a conversation engine, stream back the public assistant events, and cancel by run identity. One narrow contract for 'something that can hold a conversation'.",
    "Its value is substitution. With this port, swapping Letta for a local model, a different cloud agent, or a fake for tests is a composition-root change. Without it — which is where we are — every caller is welded to Letta's HTTP shape.",
    "It also draws a line the current code does not: public assistant text is not the same thing as reasoning, tool calls, tool results, or status events. Only the first is speakable. Today that distinction is made ad hoc in each renderer.",
  ],
  contract: {
    language: "text",
    code: `IConversationAgent   (proposed — not implemented)

  submit(turn, generationId)  -> stream of AgentEvent
  cancel(generationId)        -> void

  AgentEvent =
      assistant_text   speakable
    | reasoning        never spoken
    | tool_call        never spoken
    | tool_result      never spoken
    | status           never spoken
    | terminal         ends the stream

What exists instead (each a separate, narrow Letta strategy):

  ReceptionistIntentStrategy.evaluate(transcript)
  RouteStrategy.classify(text)
  CommandCompletenessStrategy.assess(partial)
  NoteCommandInterpreter.interpret(request)

...plus a raw fetch in the renderers:

  POST /api/letta-code-message  { agent, text } -> { ok, reply }`,
    note: "The four strategies are good narrow ports for classification. None of them is a conversation port — none streams, none cancels, and none distinguishes event kinds.",
  },
  implementations: [
    {
      name: "(none)",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "The port itself does not exist.",
    },
    {
      name: "LettaAgentAdapter",
      kind: "planned",
      file: "/home/adamsl/talking_agent_parts/",
      note: "Would be the first adapter. See the LettaAgentAdapter tab for what exists today.",
    },
    {
      name: "Direct fetch in renderers",
      kind: "current",
      file: "js/implementation/detail-renderers.js",
      note: "InputOptionsRenderer.send() POSTs /api/letta-code-message itself. This is the concrete dependency the port would remove.",
    },
    {
      name: "FakeConversationAgent",
      kind: "planned",
      file: "—",
      note: "The plan requires a fake as a first-class adapter passing the same contract tests.",
    },
  ],
  dependencies: {
    usedBy: [
      "ConversationCoordinator (planned)",
      "Today: InputOptionsRenderer and AgentsRouterRenderer, directly and concretely",
    ],
    dependsOn: ["Nothing concrete — that is the entire purpose of the port"],
    note: "This is the clearest Dependency-Inversion violation left in the voice system: high-level UI policy imports a Letta-shaped HTTP call. The 930-second timeout that callers must remember to pass is a symptom — a transport detail leaking all the way into renderer code.",
  },
  developmentStatus: {
    done: [
      "The contract is designed in the original plan.",
      "Four narrow, fail-closed Letta strategies exist and demonstrate the pattern works well in this codebase.",
      "One transport adapter (LettaClient) already isolates urllib from the strategies.",
    ],
    gaps: [
      "The port does not exist, so no alternative conversation engine can be substituted.",
      "No streaming: /api/letta-code-message returns one lump after up to 900 seconds.",
      "No cancellation by run identity.",
      "No typed event model — reasoning, tool calls and status are not distinguished from speakable text in any shared place.",
      "No shared contract test suite, so 'any adapter behaves the same' is unverified.",
    ],
  },
  tests: {
    files: [
      {
        path: "dashboard/tests/test_receptionist.py",
        count: 5,
        proves:
          "One Letta-backed strategy's prompt, strict parsing, and fail-closed behaviour — the pattern a real adapter would follow.",
      },
      {
        path: "dashboard/tests/test_note_commands.py",
        count: 27,
        proves:
          "Two more Letta strategies: malformed replies, contradictory replies, and an unreachable server all leave state untouched.",
      },
      {
        path: "js/tests/http-note-command-services.test.js",
        count: 7,
        proves:
          "The browser-side adapters validate responses and fail closed on transport errors.",
      },
    ],
    untested: [
      "The actual conversation path — POST /api/letta-code-message has no unit test at all. It is exercised only through renderer tests that stub the HTTP client.",
      "Streaming, cancellation, and event ordering: no code, no tests.",
    ],
    next: [
      "A characterization test pinning today's /api/letta-code-message request and response shape. That test is what makes extracting the port safe.",
      "A shared contract suite both a fake and the Letta adapter must pass, per the plan's Liskov requirement.",
    ],
  },
  diagrams: [
    {
      title: "Today vs. with the port",
      caption:
        "Left: policy depends on a concrete technology. Right: both depend on the contract, which is what makes a second engine possible.",
      code: `flowchart LR
  subgraph Now["Today"]
    R1["InputOptionsRenderer<br/>(high-level policy)"]
    L1["POST /api/letta-code-message<br/>(concrete Letta)"]
    R1 --> L1
  end
  subgraph Wanted["With the port"]
    R2["ConversationCoordinator<br/>(high-level policy)"]
    P{{"IConversationAgent"}}
    A1[LettaAgentAdapter]
    A2[FakeConversationAgent]
    A3["LocalModelAdapter<br/>(future)"]
    R2 --> P
    A1 -.-> P
    A2 -.-> P
    A3 -.-> P
  end`,
    },
    {
      title: "The turn the port would own",
      caption:
        "Note the event kinds: only assistant_text reaches the synthesizer. Today that filtering is re-decided in each renderer.",
      code: `sequenceDiagram
  participant CO as ConversationCoordinator
  participant ICA as IConversationAgent
  participant LAA as LettaAgentAdapter
  participant Toyota
  participant SOP as SpokenOutputPolicy
  participant TTS as SpeechSynthesizer

  CO->>ICA: submit(turn, gen-7)
  ICA->>LAA: (selected adapter)
  LAA->>Toyota: POST /v1/agents/{id}/messages
  Toyota-->>LAA: reasoning
  LAA-->>CO: reasoning (gen-7)
  CO->>SOP: gate
  SOP--xTTS: rejected — not speakable
  Toyota-->>LAA: assistant_text
  LAA-->>CO: assistant_text (gen-7)
  CO->>SOP: gate
  SOP->>TTS: speak
  Toyota-->>LAA: terminal
  LAA-->>CO: terminal (gen-7)`,
    },
  ],
  nextWork: [
    "Write a characterization test for the current /api/letta-code-message call, capturing request shape, the 930s timeout, and the { ok, reply } response.",
    "Define IConversationAgent with submit/cancel and a typed event union.",
    "Implement a fake first, then move the existing HTTP call behind LettaAgentAdapter with no behaviour change.",
    "Point InputOptionsRenderer at the port instead of fetch, removing the 930s timeout knowledge from renderer code.",
    "Add a shared contract suite that both adapters must pass.",
  ],
};
