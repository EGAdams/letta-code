import type {
  AssistantMessage,
  LettaStreamingResponse,
  ReasoningMessage,
  ToolCallMessage,
} from "@letta-ai/letta-client/resources/agents/messages";
import type { ToolReturnMessage } from "@letta-ai/letta-client/resources/tools";
import type { DrainStreamHook } from "../cli/helpers/stream";
import type {
  IAgentEventLogger,
  IAgentLoggerFactory,
  IAgentSessionLogger,
} from "./agent-event-logger";
import { RemoteAgentEventLogger } from "./remote-agent-event-logger";

export const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";

// One entry per accordion section in localhost:8080.
export const SCISSARI_LOGGER_IDS = {
  SESSION: "Scissari_Session_2026",
  THOUGHTS: "Scissari_Thoughts_2026",
  ASSISTANT: "Scissari_Assistant_2026",
  TOOL_BASH: "Scissari_Tool_Bash_2026",
  TOOL_READ: "Scissari_Tool_Read_2026",
  TOOL_EDIT: "Scissari_Tool_Edit_2026",
  TOOL_WEB: "Scissari_Tool_Web_2026",
  TOOL_OTHER: "Scissari_Tool_Other_2026",
  TOOL_RETURNS: "Scissari_ToolReturns_2026",
  APPROVALS: "Scissari_Approvals_2026",
} as const;

type LoggerKey = keyof typeof SCISSARI_LOGGER_IDS;

// Maps tool function names → logger key.
const TOOL_LOGGER_KEY: Record<string, LoggerKey> = {
  Bash: "TOOL_BASH",
  bash: "TOOL_BASH",
  Read: "TOOL_READ",
  read_file: "TOOL_READ",
  Edit: "TOOL_EDIT",
  str_replace_based_edit_tool: "TOOL_EDIT",
  Write: "TOOL_EDIT",
  write_file: "TOOL_EDIT",
  WebSearch: "TOOL_WEB",
  web_search: "TOOL_WEB",
  WebFetch: "TOOL_WEB",
  web_fetch: "TOOL_WEB",
};

const MAX_SNIPPET = 300;

// Null-safe: ToolCallDelta fields are all optional/nullable.
function snippet(s: unknown): string {
  if (typeof s !== "string") return "";
  const cleaned = s.replace(/\n+/g, " ").trim();
  return cleaned.length > MAX_SNIPPET ? `${cleaned.slice(0, MAX_SNIPPET)}…` : cleaned;
}

// Returns null for partial delta chunks that carry only argument fragments (no name yet).
function toolNameFromChunk(chunk: ToolCallMessage): string | null {
  const tc = chunk.tool_call as { name?: string | null };
  return typeof tc?.name === "string" && tc.name ? tc.name : null;
}

function contentText(content: AssistantMessage["content"]): string {
  if (typeof content === "string") return content;
  return content
    .map((p) =>
      typeof p === "object" && p !== null && "text" in p
        ? String((p as { text?: unknown }).text ?? "")
        : "",
    )
    .join(" ");
}

function formatChunk(chunk: LettaStreamingResponse): string | null {
  switch (chunk.message_type) {
    case "reasoning_message": {
      const r = chunk as ReasoningMessage;
      return `[thought] ${snippet(r.reasoning)}`;
    }
    case "assistant_message": {
      const a = chunk as AssistantMessage;
      return `[assistant] ${snippet(contentText(a.content))}`;
    }
    case "tool_call_message": {
      const t = chunk as ToolCallMessage;
      const name = toolNameFromChunk(t);
      // Skip pure argument-delta chunks that haven't received the name yet.
      if (!name) return null;
      const tc = t.tool_call as { arguments?: unknown };
      const args = snippet(tc.arguments);
      return `[tool_call:${name}] ${args}`;
    }
    case "tool_return_message": {
      const tr = chunk as unknown as ToolReturnMessage;
      return `[tool_return] ${snippet(tr.tool_return)}`;
    }
    case "approval_request_message": {
      const id = (chunk as { id?: string }).id ?? "?";
      return `[approval_request] id=${id}`;
    }
    default:
      return null;
  }
}

class ScissariLoggerFactory implements IAgentLoggerFactory {
  private readonly loggers = new Map<string, IAgentEventLogger>();

  constructor() {
    for (const id of Object.values(SCISSARI_LOGGER_IDS)) {
      this.loggers.set(id, new RemoteAgentEventLogger(id));
    }
  }

  getLogger(chunk: LettaStreamingResponse): IAgentEventLogger | null {
    switch (chunk.message_type) {
      case "reasoning_message":
        return this.loggers.get(SCISSARI_LOGGER_IDS.THOUGHTS) ?? null;
      case "assistant_message":
        return this.loggers.get(SCISSARI_LOGGER_IDS.ASSISTANT) ?? null;
      case "tool_call_message": {
        const name = toolNameFromChunk(chunk as ToolCallMessage) ?? "";
        const key: LoggerKey = TOOL_LOGGER_KEY[name] ?? "TOOL_OTHER";
        return this.loggers.get(SCISSARI_LOGGER_IDS[key]) ?? null;
      }
      case "tool_return_message":
        return this.loggers.get(SCISSARI_LOGGER_IDS.TOOL_RETURNS) ?? null;
      case "approval_request_message":
        return this.loggers.get(SCISSARI_LOGGER_IDS.APPROVALS) ?? null;
      default:
        return null;
    }
  }

  getSessionLogger(): IAgentEventLogger {
    // SESSION is always present — constructed in the constructor.
    return this.loggers.get(SCISSARI_LOGGER_IDS.SESSION) as IAgentEventLogger;
  }

  async initAll(): Promise<void> {
    await Promise.all([...this.loggers.values()].map((l) => l.init().catch(() => {})));
  }

  async clearAll(): Promise<void> {
    await Promise.all(
      [...this.loggers.values()].map((l) => l.clear("ready.").catch(() => {})),
    );
  }
}

// Plugs into the drainStream onChunkProcessed hook to stream every
// Scissari agent event into a dedicated localhost:8080 accordion section.
export class ScissariSessionLogger implements IAgentSessionLogger {
  private readonly factory = new ScissariLoggerFactory();
  private ready = false;

  // Arrow property — keeps `this` bound when used as a callback.
  // Try-catch is mandatory: logging must never interrupt stream processing.
  readonly drainHook: DrainStreamHook = (ctx) => {
    if (!this.ready) return undefined;
    try {
      const msg = formatChunk(ctx.chunk);
      if (msg) {
        this.factory.getLogger(ctx.chunk)?.log(msg).catch(() => {});
      }
    } catch {
      // silently discard — logging errors must not affect the agent
    }
    return undefined;
  };

  async onSessionStart(agentId: string): Promise<void> {
    try {
      await this.factory.initAll();
      this.ready = true;
      await this.factory.getSessionLogger().log(`session started: ${agentId}`);
    } catch {
      // logger API unavailable — degrade silently
    }
  }

  async onSessionEnd(): Promise<void> {
    if (!this.ready) return;
    this.ready = false;
    try {
      await this.factory.getSessionLogger().log("session ended");
    } catch {}
  }
}
