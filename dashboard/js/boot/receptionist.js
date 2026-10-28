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
//
// Toyota has two brains, and the server picks which one on page load
// (`conversation_backend` from /api/receptionist-agent):
//
//   receptionist-team -> /api/receptionist-turn, the receptionist_team sidecar
//                        in ~/agent_blocks: LanceDB conversation memory plus
//                        delegation to the finance_team roles. Preferred.
//   letta             -> /api/letta-code-stream, the original Letta Code CLI,
//                        used when the sidecar is down or pinned off.
//
// Both routes emit the same NDJSON envelope deliberately, so this is an
// endpoint swap on one adapter rather than two adapters. Everything above the
// conversationAgent port — mic, continuous listening, sentence segmentation,
// edge-tts playback — is identical either way, and lives in
// receptionist-desk.js, which Sydney's Agent Management page shares.

import {
  FRONT_DESK_WINDOW,
  InputOptionsRenderer,
  StreamingLettaAgentAdapter,
} from "../implementation/index.js";
import { createOperationalConversation } from "../implementation/receptionist_work/dist/index.js";
import { recorderFactoryForAgent } from "./pipecat-voice-pilot.js";
import { ReceptionistDesk } from "./receptionist-desk.js";

export async function startReceptionist({
  http,
  speech,
  storage = globalThis.localStorage,
  doc = globalThis.document,
  recorderFactoryBuilder = recorderFactoryForAgent,
  rendererFactory = (options) => new InputOptionsRenderer(options),
  listenerFactory,
  workAgentFactory = createOperationalConversation,
  win = globalThis.window,
  // Toyota wakes up paused (blinking Play) so she never startles anyone; see
  // ReceptionistDesk for the gate and her own synthesizer.
  playbackControl,
  speechFactory,
}) {
  let agentId;
  let voiceMediaBackend = "whisper";
  let conversationBackend = "letta";
  try {
    const d = await http.getJSON("/api/receptionist-agent");
    if (!d?.ok || !d.agent_id) return;
    agentId = d.agent_id;
    voiceMediaBackend = d.voice_media_backend;
    conversationBackend = d.conversation_backend ?? "letta";
  } catch {
    return;
  }
  // An unrecognized value falls back to the Letta endpoint rather than
  // guessing at a route that may not exist — a wrong guess here is a mute box.
  const endpoint =
    conversationBackend === "receptionist-team"
      ? "/api/receptionist-turn"
      : "/api/letta-code-stream";
  const inner = new StreamingLettaAgentAdapter({ storage, endpoint });
  const operations =
    conversationBackend === "receptionist-team"
      ? workAgentFactory({ inner, http, doc })
      : null;
  // "Toyota, bring up Mazda" opens Mazda's page in its own window. Naming this
  // one lets Mazda put Toyota back on the horn without reloading her. A popup
  // keeps the name it was opened with, so only an unnamed window claims it.
  if (win && !win.name) win.name = FRONT_DESK_WINDOW;
  const desk = new ReceptionistDesk(
    {
      name: "Toyota",
      agentId,
      boxId: "receptionist-box",
      conversationAgent: operations?.agent || inner,
      intentPolicy: {
        evaluate: (text) =>
          http.postJSON(
            "/api/receptionist-intent",
            { text },
            { timeout: 15000 },
          ),
      },
      pipecatSelected: voiceMediaBackend === "pipecat",
    },
    {
      http,
      storage,
      doc,
      win,
      recorderFactoryBuilder,
      ...(listenerFactory ? { listenerFactory } : {}),
      ...(playbackControl !== undefined ? { playbackControl } : {}),
      ...(speechFactory ? { speechFactory } : {}),
      speech,
    },
  );
  const rendered = rendererFactory(desk.rendererOptions()).render(
    "receptionist-box",
    agentId,
  );
  operations?.mount();
  if (!operations) {
    const notice = doc.createElement("p");
    notice.textContent =
      "Toyota is using the Letta conversation backend. Resumable workflow tools are unavailable until the receptionist service returns.";
    doc.getElementById("receptionist-box")?.appendChild(notice);
  }
  return rendered;
}
