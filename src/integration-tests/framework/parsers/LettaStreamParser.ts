import type { IStreamEventParser, JsonObject } from "../IStreamEventParser";

/** Parses the Letta stream_event NDJSON envelope produced by --output-format stream-json. */
export class LettaStreamParser implements IStreamEventParser {
  parseLines(stdout: string): JsonObject[] {
    return stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .flatMap((line) => {
        try {
          return [JSON.parse(line) as JsonObject];
        } catch {
          return [];
        }
      });
  }

  extractRunIds(events: JsonObject[]): string[] {
    const ids = new Set<string>();
    for (const ev of events) {
      const se = ev.event;
      if (
        ev.type === "stream_event" &&
        se &&
        typeof se === "object" &&
        "run_id" in se &&
        typeof (se as JsonObject).run_id === "string"
      ) {
        ids.add((se as JsonObject).run_id as string);
      }
    }
    return [...ids];
  }

  extractResultText(events: JsonObject[]): string {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (
        ev?.type === "result" &&
        typeof ev.result === "string" &&
        (ev.result as string).trim()
      ) {
        return ev.result as string;
      }
    }
    return "";
  }

  extractMessageTypes(events: JsonObject[]): string[] {
    const types: string[] = [];
    for (const ev of events) {
      const se = ev.event;
      if (
        ev.type === "stream_event" &&
        se &&
        typeof se === "object" &&
        "message_type" in se &&
        typeof (se as JsonObject).message_type === "string"
      ) {
        types.push((se as JsonObject).message_type as string);
      }
    }
    return types;
  }

  extractToolReturnEvents(events: JsonObject[]): JsonObject[] {
    return events.filter((ev) => {
      const se = ev.event;
      return (
        ev.type === "stream_event" &&
        se &&
        typeof se === "object" &&
        (se as JsonObject).message_type === "tool_return_message"
      );
    });
  }

  findFinalResult(events: JsonObject[]): JsonObject | undefined {
    return events.find((ev) => ev.type === "result");
  }

  extractMessageText(events: JsonObject[]): string {
    const parts: string[] = [];
    for (const ev of events) {
      if (ev.type === "message" && ev.message_type === "assistant_message") {
        const content = ev.content;
        if (typeof content === "string") {
          parts.push(content);
        } else if (Array.isArray(content)) {
          for (const part of content as unknown[]) {
            if (
              part &&
              typeof part === "object" &&
              "text" in (part as object) &&
              typeof (part as JsonObject).text === "string"
            ) {
              parts.push((part as JsonObject).text as string);
            }
          }
        }
      }
    }
    return parts.join("");
  }
}
