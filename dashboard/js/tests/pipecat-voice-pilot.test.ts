import { describe, expect, test } from "bun:test";
import {
  PIPECAT_PILOT_AGENT_KEY,
  recorderFactoryForAgent,
} from "../boot/pipecat-voice-pilot.js";

const response = {
  ok: true,
  status: 200,
  json: async () => ({
    ok: true,
    raw_transcript: "hello",
    cleaned_text: "hello",
  }),
};

describe("Pipecat voice pilot composition", () => {
  test("sends pilot headers only for the selected browser agent", async () => {
    const storage = {
      getItem: (key: string) =>
        key === PIPECAT_PILOT_AGENT_KEY ? "agent-a" : null,
    };
    const calls: Record<string, string>[] = [];
    const fetch = async (
      _url: string,
      init: { headers: Record<string, string> },
    ) => {
      calls.push(init.headers);
      return response;
    };
    const recording = new Blob(["audio"], { type: "audio/webm" });

    await recorderFactoryForAgent(
      "agent-a",
      storage,
    )({ fetch }).transcribe(recording);
    await recorderFactoryForAgent(
      "agent-b",
      storage,
    )({ fetch }).transcribe(recording);

    expect(calls[0]?.["X-Voice-Media-Backend"]).toBe("pipecat");
    expect(calls[0]?.["X-Voice-Agent-Id"]).toBe("agent-a");
    expect(calls[1]?.["X-Voice-Media-Backend"]).toBeUndefined();
  });
});
