# Letta stream transport

The server adapter will expose the CLI's existing NDJSON stream rather than
waiting for the final JSON object. The browser adapter validates each line and
maps provider events to the shared `AgentEvent` vocabulary.

```mermaid
sequenceDiagram
  participant Adapter as StreamingLettaAgentAdapter
  participant API as Streaming HTTP endpoint
  participant Runner as LettaCodeStreamRunner
  participant CLI as Letta Code CLI
  participant Letta

  Adapter->>API: POST turn and conversation id
  API->>API: validate Pydantic request model
  API->>Runner: start stream command
  Runner->>CLI: output format stream-json with partial messages
  CLI->>Letta: start agent turn
  Letta-->>CLI: streamed response chunks
  CLI-->>Runner: NDJSON stream events
  Runner-->>API: validated Pydantic stream records
  API-->>Adapter: application/x-ndjson body
  Adapter->>Adapter: map wire record to AgentEvent
  Note over Adapter: unknown and malformed records fail closed
  CLI-->>Runner: result record
  Runner-->>API: terminal record and conversation id
  API-->>Adapter: close response body
  opt User interrupts the generation
    Adapter-xAPI: abort response stream
    API-xRunner: client disconnected
    Runner-xCLI: terminate process group
  end
```
