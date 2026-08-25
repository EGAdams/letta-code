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
// The command channel below the note gets a THIRD listener: the two boxes are
// two conversations (dictate the note / instruct Toyota about it), so they
// start and stop independently. The channel's collaborators are the two HTTP
// adapters — swapping either for a local implementation is a change here and
// nowhere else. See js/abstract/voice-command-channel.js.

import {
  BrowserSpeechRecognitionListener,
  HttpCompletenessDetector,
  HttpNoteCommandInterpreter,
  InputOptionsRenderer,
  NoteCommandPanelRenderer,
  ReadOnlyNoteSurface,
} from "../implementation/index.js";

export async function startReceptionist({ http, speech }) {
  let agentId;
  try {
    const d = await http.getJSON("/api/receptionist-agent");
    if (!d?.ok || !d.agent_id) return;
    agentId = d.agent_id;
  } catch {
    return;
  }
  const api = new InputOptionsRenderer({
    http,
    speech,
    agentName: "Toyota",
    agentId,
    listener: new BrowserSpeechRecognitionListener(),
    receptionistIntentPolicy: {
      evaluate: (text) =>
        http.postJSON("/api/receptionist-intent", { text }, { timeout: 15000 }),
    },
    // Toyota's box is a note document, not a message box: read-only, white on
    // black. Editing it happens by voice through the command channel below.
    surfaceFactory: (opts) => new ReadOnlyNoteSurface(opts),
  }).render("receptionist-box", agentId);
  if (!api) return;

  new NoteCommandPanelRenderer({
    note: api.note,
    listener: new BrowserSpeechRecognitionListener(),
    completenessDetector: new HttpCompletenessDetector({ http }),
    commandInterpreter: new HttpNoteCommandInterpreter({ http }),
  }).render("note-command-box");
}
