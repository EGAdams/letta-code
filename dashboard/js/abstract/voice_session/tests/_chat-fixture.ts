import { AgentEventKind } from "../../../abstract/conversation-agent.interface.js";
import { SpokenOutputPolicy } from "../../../abstract/spoken-output-policy.js";
import { ChatDetailRenderer } from "../../../implementation/detail-renderers.js";
import { FakeDocument } from "../../../tests/_fake-dom.js";
import { VoiceSession } from "../src/voice-session.ts";

export function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

export function build(
  events: Array<{ kind: string; text: string }> = [],
  speechOverride?: object,
) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "chat";
  doc.add(container);
  const session = new VoiceSession();
  const entered = deferred();
  const release = deferred();
  const spoken: string[] = [];
  const cancelled: string[] = [];
  const statuses: string[] = [];
  const conversationAgent = {
    async *submit(_turn: unknown, generationId: string) {
      entered.resolve();
      await release.promise;
      for (const event of events) yield { ...event, generationId };
      yield { kind: AgentEventKind.TERMINAL, text: "", generationId };
    },
    cancel(generationId: string) {
      cancelled.push(generationId);
    },
  };
  const renderer = new ChatDetailRenderer({
    conversationAgent,
    voiceSession: session,
    spokenOutputPolicy: new SpokenOutputPolicy({ session }),
    speech: speechOverride ?? {
      supported: true,
      speak(text: string) {
        spoken.push(text);
        return { pending: Promise.resolve("speech") };
      },
      cancel() {},
    },
    agentName: "Scissari",
    doc,
    storage: { getItem: () => "1", setItem() {} },
    recorderFactory: () => ({ isRecording: false, start: async () => true }),
    onStatus: (_id: string, status: string) => statuses.push(status),
  });
  const ui = renderer.render("chat", "agent-scissari");
  if (!ui) throw new Error("Chat did not render");
  return {
    container,
    session,
    entered,
    release,
    spoken,
    cancelled,
    statuses,
    ui,
  };
}
