import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../../../abstract/conversation-agent.interface.js";
import { SpokenOutputPolicy } from "../../../abstract/spoken-output-policy.js";
import { InputOptionsRenderer } from "../../../implementation/detail-renderers.js";
import { FakeDocument } from "../../../tests/_fake-dom.js";
import { VoiceSession } from "../src/voice-session.ts";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function build(speechOverride?: object) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "input-options";
  const session = new VoiceSession();
  const policy = new SpokenOutputPolicy({ session });
  const entered = deferred();
  const release = deferred();
  const submitted: string[] = [];
  const spoken: string[] = [];
  const conversationAgent = {
    async *submit(_turn: unknown, generationId: string) {
      submitted.push(generationId);
      entered.resolve();
      await release.promise;
      yield {
        kind: AgentEventKind.ASSISTANT_TEXT,
        text: "The old answer arrived late.",
        generationId,
      };
    },
    cancel(_generationId: string) {},
  };
  const storage = { getItem: () => null, setItem: () => {} };
  const renderer = new InputOptionsRenderer({
    http: {
      getJSON: async () => ({ ok: false, options: [] }),
      postJSON: async () => ({ ok: true }),
    },
    conversationAgent,
    voiceSession: session,
    spokenOutputPolicy: policy,
    speech: speechOverride ?? {
      supported: true,
      speak: (text: string) => {
        spoken.push(text);
        return { pending: Promise.resolve("speech") };
      },
    },
    agentName: "Mazda",
    doc,
    storage,
    recorderFactory: () => ({ isRecording: false }),
  });
  const ui = renderer.render("input-options", "agent-mazda");
  if (!ui) throw new Error("Input Options did not render");
  return { session, entered, release, submitted, spoken, ui };
}

describe("Input Options voice session", () => {
  test("interrupting active playback cancels its handle and retires the turn", async () => {
    const finished = deferred();
    const cancelled: string[] = [];
    const speech = {
      supported: true,
      speak: () => ({
        pending: Promise.resolve("edge-tts"),
        finished: finished.promise,
        cancel: () => {
          cancelled.push("cancelled");
          finished.resolve();
        },
      }),
    };
    const { session, entered, release, ui } = build(speech);
    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    release.resolve();
    await sending;
    await Promise.resolve();
    expect(session.state).toBe("speaking");

    session.interrupt();
    expect(cancelled).toEqual(["cancelled"]);
    expect(session.state).toBe("interrupted");
    await finished.promise;
    expect(session.currentGeneration).toBeNull();
  });

  test("a completed playback retires the speaking turn only when audio ends", async () => {
    const finished = deferred();
    const speech = {
      supported: true,
      speak: () => ({
        pending: Promise.resolve("edge-tts"),
        finished: finished.promise,
        cancel: () => {},
      }),
    };
    const { session, entered, release, ui } = build(speech);
    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    release.resolve();
    await sending;
    await Promise.resolve();
    expect(session.state).toBe("speaking");
    finished.resolve();
    await finished.promise;
    await Promise.resolve();
    expect(session.state).toBe("listening");
  });

  test("sending a second turn stops the first answer already playing", async () => {
    const finished = [deferred(), deferred()];
    const cancelled: number[] = [];
    let calls = 0;
    const speech = {
      supported: true,
      speak: () => {
        const index = calls++;
        return {
          pending: Promise.resolve("edge-tts"),
          finished: finished[index].promise,
          cancel: () => {
            cancelled.push(index);
            finished[index].resolve();
          },
        };
      },
    };
    const { session, entered, release, ui } = build(speech);
    const first = ui.send({ textOverride: "March" });
    await entered.promise;
    release.resolve();
    await first;
    const second = ui.send({ textOverride: "April" });
    await second;
    expect(cancelled).toEqual([0]);
    expect(session.state).toBe("speaking");
    finished[1].resolve();
    await finished[1].promise;
    await Promise.resolve();
    expect(session.state).toBe("listening");
  });

  test("an interrupted turn's late reply never reaches speech", async () => {
    const { session, entered, release, submitted, spoken, ui } = build();
    // A prior turn is in flight when the renderer is rebuilt. The new Send
    // should supersede it using this same session, then carry its new id.
    session.startListening();
    session.beginTurn();

    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    const interrupted = session.interrupt();
    release.resolve();
    await sending;

    expect(spoken).toEqual([]);
    expect(submitted).toEqual([interrupted]);
  });

  test("closing a session while an answer is pending keeps it silent", async () => {
    const { session, entered, release, spoken, ui } = build();
    const sending = ui.send({ textOverride: "Ask about March" });
    await entered.promise;
    session.close();
    release.resolve();
    await sending;

    expect(spoken).toEqual([]);
  });

  test("a current answer is spoken and its turn is completed", async () => {
    const { session, entered, release, spoken, ui } = build();
    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    release.resolve();
    await sending;
    await Promise.resolve();

    expect(spoken).toEqual(["The old answer arrived late."]);
    expect(session.currentGeneration).toBeNull();
  });
});
