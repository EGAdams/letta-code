// receptionist.js — Toyota, the Home-screen receptionist.
//
// Same Input Options widget as any agent's Agent Management page (reuses
// InputOptionsRenderer as-is), but pinned to the fixed "Toyota" agent and
// paired with its own ContinuousListener — separate from the Agents tab's
// router listener. Listening is opt-in via the "Start Listening" button
// InputOptionsRenderer renders when given a listener (no name-detection
// hand-off; this box only ever talks to Toyota): every final recognized chunk
// while listening is sent straight to her.
//
// Toyota's box used to be a read-only note document edited by a separate
// spoken command channel (#note-command-box, NoteCommandPanelRenderer). It is
// now an ordinary typeable/dictatable message box like every other agent's —
// Send and Save Note both clear it — so that second box and its listener are
// gone. The underlying command-channel classes (js/abstract/voice-command-
// channel.js and friends) stay in the tree; nothing else references them.

import {
  BrowserSpeechRecognitionListener,
  EditableDarkNoteSurface,
  InputOptionsRenderer,
  LettaAgentAdapter,
  SpokenOutputPolicy,
  VoiceSession,
} from "../implementation/index.js";
import { recorderFactoryForAgent } from "./pipecat-voice-pilot.js";

export async function startReceptionist({
  http,
  speech,
  storage = globalThis.localStorage,
  doc = globalThis.document,
  recorderFactoryBuilder = recorderFactoryForAgent,
  rendererFactory = (options) => new InputOptionsRenderer(options),
  listenerFactory = () => new BrowserSpeechRecognitionListener(),
}) {
  let agentId;
  let voiceMediaBackend = "whisper";
  try {
    const d = await http.getJSON("/api/receptionist-agent");
    if (!d?.ok || !d.agent_id) return;
    agentId = d.agent_id;
    voiceMediaBackend = d.voice_media_backend;
  } catch {
    return;
  }
  const voiceSession = new VoiceSession();
  return rendererFactory({
    http,
    conversationAgent: new LettaAgentAdapter({
      http,
      storage,
    }),
    voiceSession,
    spokenOutputPolicy: new SpokenOutputPolicy({ session: voiceSession }),
    speech,
    agentName: "Toyota",
    agentId,
    storage,
    doc,
    recorderFactory: recorderFactoryBuilder(agentId, storage, {
      serverSelected: voiceMediaBackend === "pipecat",
    }),
    listener: listenerFactory(),
    receptionistIntentPolicy: {
      evaluate: (text) =>
        http.postJSON("/api/receptionist-intent", { text }, { timeout: 15000 }),
    },
    // Same white-on-black look as before, now editable and clearing like any
    // other agent's message box.
    surfaceFactory: (opts) => new EditableDarkNoteSurface(opts),
  }).render("receptionist-box", agentId);
}
