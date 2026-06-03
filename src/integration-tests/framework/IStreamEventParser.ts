export type JsonObject = Record<string, unknown>;

/**
 * Abstracts over different agent wire-format envelopes.
 * The Letta concrete implementation lives in parsers/LettaStreamParser.ts.
 * A future agent using a different protocol would supply its own implementation.
 */
export interface IStreamEventParser {
  /** Parse newline-delimited JSON lines from CLI stdout. */
  parseLines(stdout: string): JsonObject[];
  /** Extract Letta run IDs from stream_event envelopes. */
  extractRunIds(events: JsonObject[]): string[];
  /** Text from the final result event. */
  extractResultText(events: JsonObject[]): string;
  /** List of message_type values seen in stream_event envelopes. */
  extractMessageTypes(events: JsonObject[]): string[];
  /** All tool_return_message stream events. */
  extractToolReturnEvents(events: JsonObject[]): JsonObject[];
  /** The final {type:"result"} event, if present. */
  findFinalResult(events: JsonObject[]): JsonObject | undefined;
  /** Concatenated text from assistant_message events. */
  extractMessageText(events: JsonObject[]): string;
}
