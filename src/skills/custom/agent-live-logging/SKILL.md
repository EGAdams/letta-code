---
name: agent-live-logging
description: >
  Wire a Letta agent's stream events (thoughts, tool calls, tool returns, assistant messages,
  approvals) into the localhost:8080 log viewer, one accordion section per event type.
  Covers the full interface-first design: IAgentEventLogger / IAgentLoggerFactory /
  IAgentSessionLogger, the RemoteAgentEventLogger concrete class, Scissari-specific wiring,
  and how to extend it for additional agents. Use this skill whenever the user asks about
  live-logging an agent to the viewer, adding new accordion sections, or extending the logging
  system to cover a new agent.
---

# Agent Live-Logging Skill

## What this skill does

Adds per-event-type accordion sections to `localhost:8080` for any Letta agent, so every
thought, tool call, tool return, assistant message, and approval request appears in its own
collapsible section in real time while the agent runs.

---

## Architecture overview

```
App.tsx  ──useEffect──▶  createAgentSessionLogger(agentId)
                              │
                              ▼
                     ScissariSessionLogger          ◀── IAgentSessionLogger
                              │
                     .drainHook  ◀─── passed as onChunkProcessed to drainStreamWithResume()
                              │
                              ▼
                     ScissariLoggerFactory          ◀── IAgentLoggerFactory
                        │  routes chunk.message_type + tool name
                        ▼
              RemoteAgentEventLogger (×10)         ◀── IAgentEventLogger
                  │  wraps RemoteLogger
                  ▼
          localhost:8080 accordion per event type
```

---

## Source files

| File | Purpose |
|---|---|
| `src/logger/agent-event-logger.ts` | Three interfaces: `IAgentEventLogger`, `IAgentLoggerFactory`, `IAgentSessionLogger` |
| `src/logger/remote-agent-event-logger.ts` | `RemoteAgentEventLogger` — wraps `RemoteLogger`, implements `IAgentEventLogger` |
| `src/logger/scissari-session-logger.ts` | `ScissariSessionLogger` + `ScissariLoggerFactory` + `SCISSARI_LOGGER_IDS` constants |
| `src/logger/agent-session-logger-factory.ts` | `createAgentSessionLogger(agentId)` — returns the right logger or null |

---

## Interfaces (program to these, not to implementations)

```typescript
// src/logger/agent-event-logger.ts

// One accordion section in the localhost:8080 viewer
interface IAgentEventLogger {
  init(): Promise<void>;
  log(message: string): Promise<void>;
  clear(label?: string): Promise<void>;
}

// Routes each stream chunk to the correct accordion
interface IAgentLoggerFactory {
  getLogger(chunk: LettaStreamingResponse): IAgentEventLogger | null;
  initAll(): Promise<void>;
  clearAll(): Promise<void>;
}

// Plugs into drainStream via the onChunkProcessed hook
interface IAgentSessionLogger {
  readonly drainHook: DrainStreamHook;
  onSessionStart(agentId: string): Promise<void>;
  onSessionEnd(): Promise<void>;
}
```

---

## Scissari logger IDs (10 accordion sections)

Defined in `SCISSARI_LOGGER_IDS` in `scissari-session-logger.ts`.

| Constant key | Logger ID | What it logs |
|---|---|---|
| `SESSION` | `Scissari_Session_2026` | session start / end |
| `THOUGHTS` | `Scissari_Thoughts_2026` | `reasoning_message` chunks |
| `ASSISTANT` | `Scissari_Assistant_2026` | `assistant_message` chunks |
| `TOOL_BASH` | `Scissari_Tool_Bash_2026` | Bash / bash tool calls |
| `TOOL_READ` | `Scissari_Tool_Read_2026` | Read / read_file tool calls |
| `TOOL_EDIT` | `Scissari_Tool_Edit_2026` | Edit / Write / str_replace_based_edit_tool |
| `TOOL_WEB` | `Scissari_Tool_Web_2026` | WebSearch / WebFetch / web_search / web_fetch |
| `TOOL_OTHER` | `Scissari_Tool_Other_2026` | any tool not in the map above |
| `TOOL_RETURNS` | `Scissari_ToolReturns_2026` | `tool_return_message` chunks |
| `APPROVALS` | `Scissari_Approvals_2026` | `approval_request_message` chunks |

All 10 are registered in:
- `src/integration-tests/logger-helpers.ts` → `ALL_LOGGER_IDS`
- `/home/adamsl/the-factory/public/index.html` → `<accordion-section>` elements

---

## How the hook is wired into App.tsx

```typescript
// Ref holds the session logger for the current agent (null for unknown agents)
const sessionLoggerRef = useRef<IAgentSessionLogger | null>(null);

useEffect(() => {
  const logger = createAgentSessionLogger(agentId);
  sessionLoggerRef.current = logger;
  if (logger) {
    logger.onSessionStart(agentId).catch(() => {});
  }
  return () => {
    const prev = sessionLoggerRef.current;
    sessionLoggerRef.current = null;
    prev?.onSessionEnd().catch(() => {});
  };
}, [agentId]);

// Passed as the 6th argument (onChunkProcessed) to drainStreamWithResume:
return drainStreamWithResume(
  stream,
  buffersRef.current,
  refreshDerivedThrottled,
  signal,
  handleFirstMessage,
  sessionLoggerRef.current?.drainHook,   // ← was undefined before
  contextTrackerRef.current,
  highestSeqIdSeen,
);
```

### Critical: drainHook must never throw

The `drainHook` is `await`-ed inside the `for await (chunk of stream)` loop with no inner
try-catch. Any exception propagates and aborts the stream with `stopReason="error"`. The hook
always wraps its body in `try { ... } catch {}` so logging errors are silently discarded.

### Critical: ToolCallDelta nullable fields

`ToolCallMessage.tool_call` is typed `ToolCall | ToolCallDelta`. `ToolCallDelta` has all-optional
fields: `name?: string | null`, `arguments?: string | null`. Calling `s.replace(...)` on a null
value throws. The `snippet()` helper checks `typeof s !== "string"` and returns `""` for nulls.
Partial delta chunks with no name (argument-only fragments) are skipped by returning `null` from
`formatChunk`.

---

## Adding a new agent

1. **Pick logger IDs** — one per event type you want to observe (see Scissari as a template).

2. **Create a session logger** — copy `scissari-session-logger.ts` structure:
   ```typescript
   export const MY_AGENT_LOGGER_IDS = { SESSION: "MyAgent_Session_2026", ... } as const;
   export class MyAgentSessionLogger implements IAgentSessionLogger { ... }
   ```

3. **Register in the factory** (`agent-session-logger-factory.ts`):
   ```typescript
   if (agentId === MY_AGENT_ID) return new MyAgentSessionLogger();
   ```

4. **Register logger IDs** — add each ID to `ALL_LOGGER_IDS` in
   `src/integration-tests/logger-helpers.ts`.

5. **Add accordion sections** to `/home/adamsl/the-factory/public/index.html`:
   ```html
   <accordion-section
       id="accordion-section-myagent-session"
       monitored_object_id="MyAgent_Session_2026"
       data_source_location="http://100.80.49.10:8284/libraries/local-php-api/">
   </accordion-section>
   ```
   **The HTML is hardcoded — auto-registration does not exist. Both steps 4 and 5 are mandatory.**

6. **Rebuild** — source changes take effect only after `bun run build`.

---

## Tool name → logger key mapping

`TOOL_LOGGER_KEY` in `scissari-session-logger.ts` maps tool function names (as sent by the
server) to the logger key. Entries not in this map fall through to `TOOL_OTHER`.

To add a new tool mapping:
```typescript
const TOOL_LOGGER_KEY: Record<string, LoggerKey> = {
  Bash: "TOOL_BASH",
  MyNewTool: "TOOL_OTHER",   // ← add here
  ...
};
```

---

## Checklist when logging stops working

- [ ] `ready` flag in `ScissariSessionLogger` — set to `true` only after `initAll()` succeeds.
      If the logger API is unreachable, `ready` stays false and nothing is logged.
- [ ] `bun run build` — the letta.js bundle is what runs; source changes require a rebuild.
- [ ] Accordion sections in index.html — must be present for the viewer to show the row.
- [ ] Logger IDs in `ALL_LOGGER_IDS` — required for `resetAllLoggers()` to clear them.
- [ ] `snippet()` receiving null — if a new message type passes non-string content, `snippet`
      handles it gracefully (returns `""`).
- [ ] Hook throwing — the `try/catch` in `drainHook` swallows all exceptions silently; check
      `formatChunk` logic for any new `case` that might throw.
