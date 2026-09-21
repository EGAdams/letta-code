import { describe, expect, test } from "bun:test";
import {
  PIPECAT_PILOT_AGENT_KEY,
  recorderFactoryForAgent,
} from "../boot/pipecat-voice-pilot.js";
import { startReceptionist } from "../boot/receptionist.js";
import { FakeDocument } from "./_fake-dom.js";

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
  test("wires Toyota's selected media strategy into the home-screen recorder", async () => {
    const doc = new FakeDocument();
    const container = doc.createElement("section");
    container.id = "receptionist-box";
    doc.add(container);
    const storage = {
      getItem: (key: string) =>
        key === PIPECAT_PILOT_AGENT_KEY ? "toyota-id" : null,
      setItem: () => {},
    };
    const selectedRecorderFactory = () => ({ kind: "toyota-pipecat" });
    const selections: Array<
      [string, typeof storage, { serverSelected?: boolean }]
    > = [];
    let rendererOptions: Record<string, unknown> | undefined;

    await startReceptionist({
      http: {
        getJSON: async () => ({
          ok: true,
          agent_id: "toyota-id",
          name: "Toyota",
          voice_media_backend: "pipecat",
        }),
      },
      speech: { supported: false },
      storage,
      recorderFactoryBuilder: (
        agentId: string,
        selectedStorage: typeof storage,
        options: { serverSelected?: boolean },
      ) => {
        selections.push([agentId, selectedStorage, options]);
        return selectedRecorderFactory;
      },
      rendererFactory: (options: Record<string, unknown>) => {
        rendererOptions = options;
        return { render: () => ({}) };
      },
      doc,
    });

    expect(selections).toEqual([
      ["toyota-id", storage, { serverSelected: true }],
    ]);
    expect(rendererOptions?.recorderFactory).toBe(selectedRecorderFactory);
  });

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

  test("honors the server-selected Toyota pilot without a browser storage key", async () => {
    const calls: Record<string, string>[] = [];
    const fetch = async (
      _url: string,
      init: { headers: Record<string, string> },
    ) => {
      calls.push(init.headers);
      return response;
    };

    await recorderFactoryForAgent(
      "toyota-id",
      { getItem: () => null },
      { serverSelected: true },
    )({ fetch }).transcribe(new Blob(["audio"], { type: "audio/webm" }));

    expect(calls[0]?.["X-Voice-Media-Backend"]).toBe("pipecat");
    expect(calls[0]?.["X-Voice-Agent-Id"]).toBe("toyota-id");
  });
});
