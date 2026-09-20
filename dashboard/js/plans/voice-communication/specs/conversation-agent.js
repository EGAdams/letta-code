import { Status } from "../../interface-spec.js";

export const conversationAgentSpec = {
  id: "iconversationagent",
  name: "IConversationAgent",
  group: "Planned core",
  tagline:
    "The port has two adapters and a shared contract suite. Input Options now uses it.",
  status: Status.PARTIAL,
  statusNote:
    "InputOptionsRenderer sends through LettaAgentAdapter; the fake drives its renderer test. Other send paths still need adoption.",
  responsibility: [
    "Submit one user turn to a conversation engine, stream back the public assistant events, and cancel by run identity. One narrow contract for 'something that can hold a conversation'.",
    "Its value is substitution. InputOptionsRenderer already accepts a fake or Letta adapter selected at its composition root. Other callers can adopt the same contract when their reply shapes are mapped.",
    "It also draws a line the renderers do not: public assistant text is not the same thing as reasoning, tool calls, tool results, or status events. Only the first is speakable, and that is a property of the event kind, enforced once by SpokenOutputPolicy — not re-decided in each renderer.",
  ],
  contract: {
    language: "text",
    code: `ConversationAgent   js/abstract/conversation-agent.interface.js   (shipped)

  submit(turn, generationId)  -> AsyncGenerator<AgentEvent>
  cancel(generationId)        -> void   safe for an unknown generation

  ConversationTurn = { agent, text, conversationId? }
  AgentEvent       = { kind, text, generationId, name?, detail? }

  parseAgentEvent(raw, gen)   untrusted -> AgentEvent | null (fail closed)
  isSpeakable(kind)           only assistant_text

  AgentEvent kinds =
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

...plus raw fetches that other renderers still make directly:

  POST /api/letta-code-message  { agent, text } -> { ok, reply }`,
    note: "submit() is an async generator so a streaming adapter and a request/response one present the same shape — the non-streaming Letta path simply yields two events at the end. Callers write one loop either way, which is what makes the adapters substitutable.",
  },
  implementations: [
    {
      name: "ConversationAgent",
      kind: "current",
      file: "js/abstract/conversation-agent.interface.js",
      note: "The port, the AgentEvent vocabulary, and parseAgentEvent — which drops an unrecognisable event rather than guessing a kind for it.",
    },
    {
      name: "LettaAgentAdapter",
      kind: "current",
      file: "js/implementation/letta-agent-adapter.js",
      note: "The first adapter, over /api/letta-code-message. Owns the 1800s timeout and per-agent conversation resume so the renderer does not.",
    },
    {
      name: "FakeConversationAgent",
      kind: "current",
      file: "js/implementation/fake-conversation-agent.js",
      note: "Scripted adapter, and a first-class one: it passes the same contract suite as the Letta adapter, so the voice UI can be driven end to end with no server.",
    },
    {
      name: "Input Options port adoption",
      kind: "current",
      file: "js/implementation/detail-renderers.js",
      note: "InputOptionsRenderer.send() consumes assistant_text events from its injected ConversationAgent. Other renderer send paths still use direct requests.",
    },
  ],
  dependencies: {
    usedBy: [
      "InputOptionsRenderer — sends through the injected LettaAgentAdapter",
      "ConversationCoordinator (planned)",
    ],
    dependsOn: ["Nothing concrete — that is the entire purpose of the port"],
    note: "The Input Options composition root injects LettaAgentAdapter. Its request timeout and conversation resume remain inside the adapter. Other send paths still need this boundary.",
  },
  developmentStatus: {
    done: [
      "The port exists, with submit/cancel and a typed six-kind event union.",
      "Two adapters satisfy it, and a shared contract suite runs against both — that suite is the Liskov requirement made executable.",
      "Cancellation by generation id exists and is safe to call for a generation that already finished, was never submitted, or was cancelled before.",
      "parseAgentEvent fails closed on adapter output the same way the note-command parsers do: an unknown kind is dropped, and blank assistant text never becomes a spoken blank.",
      "A characterization test pins the live request shape and the 1800s client budget, which made adoption safe.",
      "Four narrow, fail-closed Letta strategies exist and demonstrate the pattern works well in this codebase.",
      "InputOptionsRenderer now calls the port and renders only assistant_text events; a fake adapter verifies the boundary without network access.",
    ],
    gaps: [
      "The other renderer send paths still fetch directly and have not adopted the port.",
      "Still no streaming: /api/letta-code-message returns one lump after up to 900 seconds, so LettaAgentAdapter yields assistant_text then terminal at the end.",
      "Cancellation is delivery-side only for the Letta adapter — the endpoint has no server-side cancel, so the work still runs and only the answer is dropped.",
      "Only assistant_text and terminal are ever produced today; reasoning, tool_call, tool_result and status are contract-only until something streams.",
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
      {
        path: "js/tests/conversation-agent-contract.js",
        count: 6,
        proves:
          "The shared suite, run against both adapters: one terminal event ends every turn, every event carries the generation it was submitted with, the answer arrives as speakable assistant text, nothing else is speakable, a cancelled turn delivers nothing and raises TurnCancelledError, and cancelling an unknown generation is safe.",
      },
      {
        path: "js/tests/letta-agent-adapter.test.js",
        count: 18,
        proves:
          "The contract suite plus the characterization: the exact POST body, the 1800s timeout, per-agent conversation resume, an explicit turn id winning over the stored one, ok:false surfacing the server error, a failed turn not overwriting the remembered conversation, and no network call at all for an empty turn.",
      },
      {
        path: "js/tests/fake-conversation-agent.test.js",
        count: 11,
        proves:
          "The contract suite plus scripting: unspeakable kinds pass through in order, a script function sees the turn, malformed entries are dropped exactly as a real adapter drops them, and cancelling mid-stream stops delivery at the next event.",
      },
      {
        path: "js/tests/spoken-output-policy.test.js",
        count: 10,
        proves:
          "The event-kind half of this contract at the point of use — see the SpokenOutputPolicy tab.",
      },
    ],
    untested: [
      "The Input Options renderer is covered by a fake-agent test; other send paths have not been moved to the port.",
      "Streaming and event ordering beyond two events: no adapter streams yet.",
    ],
    next: [
      "A renderer test for each remaining send path as that path adopts the port.",
      "A third adapter — even a deliberately odd one — to prove the contract suite catches a divergence rather than just describing the two adapters that exist.",
    ],
  },
  diagrams: [
    {
      title: "The live Input Options boundary",
      caption:
        "The composition root selects the adapter. The renderer consumes typed assistant events and never builds a Letta request.",
      code: `flowchart LR
  BOOT["Agent detail boot"] -->|constructs| A1[LettaAgentAdapter]
  R["InputOptionsRenderer"] --> P{{"ConversationAgent port"}}
  A1 -.satisfies.-> P
  FAKE[FakeConversationAgent] -.satisfies.-> P
  A1 --> HTTP["POST /api/letta-code-message"]`,
    },
    {
      title: "The Input Options turn through the port",
      caption:
        "The current endpoint returns one reply at the end. InputOptionsRenderer accepts only assistant_text; the session and spoken-output policy have not been wired yet.",
      code: `sequenceDiagram
  participant UI as InputOptionsRenderer
  participant ICA as ConversationAgent
  participant LAA as LettaAgentAdapter
  participant HTTP as Dashboard HTTP
  participant Letta

  UI->>ICA: submit(turn, gen-7)
  ICA->>LAA: (selected adapter)
  LAA->>HTTP: POST /api/letta-code-message
  HTTP->>Letta: run agent turn
  Letta-->>HTTP: assistant reply
  HTTP-->>LAA: ok, reply, conversation id
  LAA-->>UI: assistant_text (gen-7)
  LAA-->>UI: terminal (gen-7)
  UI->>UI: render and speak assistant text`,
    },
  ],
  nextWork: [
    "InputOptionsRenderer now uses the port. Next give it a VoiceSession and SpokenOutputPolicy so late replies cannot be spoken.",
    "Do the same for AgentsRouterRenderer.",
    "Thread a VoiceSession generation id through both, so replies pass SpokenOutputPolicy before reaching the synthesizer.",
    "Give the adapter real streaming once the Letta server's streaming is usable — the port shape already allows it, so that becomes an adapter change and nothing else.",
  ],
};
