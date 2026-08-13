import { Status } from "../../interface-spec.js";

export const languageProcessorSpec = {
  id: "language-processor",
  name: "LanguageProcessor",
  group: "Superseded prototype",
  tagline:
    "The prototype's do-everything LLM class. Replaced by five narrow, fail-closed strategies.",
  status: Status.SUPERSEDED,
  statusNote:
    "The plan explicitly says: do not port. Superseded, and better for it.",
  responsibility: [
    "In the prototype: construct the OpenAI client, hold the system prompt, store conversation history, enforce token policy, translate errors, and detect exit commands — all in one class.",
    "That is at least five reasons to change, and the plan's audit flagged it as the clearest Single Responsibility violation in the prototype.",
    "The shipped system replaced it with several small strategies that each answer exactly one question and share one shape: clear the agent's history, send one strict-JSON prompt, parse strictly, fail closed. None of them holds conversation state, and none constructs its own client.",
  ],
  contract: {
    language: "python",
    code: `LanguageProcessor   voice_agent/language_processor/language_processor.py

  process(user_input, use_history=True) -> str
  clear_history() / set_system_prompt() / get_history_length()
  export_history() / import_history()
  is_exit_command(text) -> bool

Replaced by (each one question, one answer):

  CleanupStrategy.clean(transcript)            -> str
  ReceptionistIntentStrategy.evaluate(text)    -> {addressed, cleaned_text}
  RouteStrategy.classify(text)                 -> {agent, remainder}
  CommandCompletenessStrategy.assess(partial)  -> CommandCompleteness
  NoteCommandInterpreter.interpret(request)    -> NoteCommandIntent`,
  },
  implementations: [
    {
      name: "LanguageProcessor",
      kind: "deprecated",
      file: "voice_agent/language_processor/language_processor.py",
      note: "Prototype only. Constructs its own OpenAI client.",
    },
    {
      name: "LettaAgentCleanup",
      kind: "current",
      file: "voice/cleanup.py",
      note: "Successor for transcript tidying.",
    },
    {
      name: "LettaReceptionistIntentStrategy",
      kind: "current",
      file: "voice/receptionist.py",
      note: "Successor for 'is Toyota being addressed'.",
    },
    {
      name: "LettaAgentRouteStrategy",
      kind: "current",
      file: "router/classify.py",
      note: "Successor for agent-name detection.",
    },
    {
      name: "LettaCommandCompletenessStrategy",
      kind: "current",
      file: "voice/note_completeness.py",
      note: "Successor for turn-end judgement.",
    },
    {
      name: "LettaNoteCommandInterpreter",
      kind: "current",
      file: "voice/note_interpreter.py",
      note: "Successor for instruction interpretation.",
    },
  ],
  dependencies: {
    usedBy: ["VoiceAgent (prototype only)"],
    dependsOn: ["openai SDK, directly constructed inside the class"],
    note: "The successors depend on an injected client with three methods, never on a concrete SDK. That is the difference that makes all five testable offline.",
  },
  developmentStatus: {
    done: [
      "Fully superseded. Every job it did has a narrower home in shipped, tested code.",
      "The fail-closed convention its successors share is now consistent across all five.",
    ],
    gaps: [
      "One capability was dropped rather than replaced: multi-turn conversation history. Every shipped strategy clears history deliberately, so nothing in the voice system currently holds a conversation across turns.",
      "That gap is exactly what IConversationAgent + VoiceSession are for. Until they exist, voice interaction is stateless request/response.",
    ],
  },
  tests: {
    files: [
      {
        path: "dashboard/tests/test_cleanup.py",
        count: 7,
        proves:
          "Cleanup falls back to the raw transcript rather than losing speech.",
      },
      {
        path: "dashboard/tests/test_receptionist.py",
        count: 5,
        proves:
          "Invented model output is refused; only clearly-addressed speech is acted on.",
      },
      {
        path: "dashboard/tests/test_router_classify.py",
        count: 14,
        proves:
          "Exact-name matching precedes any LLM call; ambiguity never guesses.",
      },
      {
        path: "dashboard/tests/test_note_commands.py",
        count: 27,
        proves:
          "Completeness and interpretation both fail closed on malformed replies.",
      },
    ],
    untested: [
      "Nothing tests the successors as a family — there is no shared contract suite asserting all five behave the same way on a malformed reply, even though they all claim to.",
    ],
    next: [
      "A shared 'fail-closed contract' test parameterised over all five strategies. Today each file re-proves the same property separately, which is duplication that will drift.",
    ],
  },
  diagrams: [
    {
      title: "One class became five strategies",
      caption:
        "Each successor answers one question with one strict-JSON call and no retained history.",
      code: `flowchart LR
  LP["LanguageProcessor<br/>(5+ reasons to change)"]
  LP --> A["CleanupStrategy<br/>tidy the transcript"]
  LP --> B["ReceptionistIntentStrategy<br/>addressed to Toyota?"]
  LP --> C["RouteStrategy<br/>which agent?"]
  LP --> D["CommandCompletenessStrategy<br/>finished speaking?"]
  LP --> E["NoteCommandInterpreter<br/>what does it mean?"]
  LP -.->|"dropped, not replaced"| F["conversation history<br/>needs VoiceSession"]
  style LP stroke-dasharray: 5 4
  style F stroke:#9b2c39,color:#9b2c39`,
    },
    {
      title: "The shared shape every successor follows",
      caption:
        "Identical in all five. The duplication is currently re-tested per file rather than proven once as a contract.",
      code: `sequenceDiagram
  participant S as Any Letta strategy
  participant LC as LettaClient
  participant Agent as Letta agent

  S->>LC: clear_messages(agent)
  Note over S,LC: history cleared so every<br/>call starts fresh
  S->>LC: send_message(agent, strict JSON prompt)
  Agent-->>LC: reply text
  LC-->>S: response
  alt reply parses and is well-formed
    S-->>S: typed result
  else anything else
    S-->>S: fail-closed default
  end`,
    },
  ],
  nextWork: [
    "Extract the shared fail-closed behaviour into one contract test run against all five strategies.",
    "When IConversationAgent lands, decide deliberately whether multi-turn history returns — it was dropped, not designed away.",
  ],
};
