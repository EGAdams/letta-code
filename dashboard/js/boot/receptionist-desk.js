// receptionist-desk.js — the front-desk mechanics every receptionist_team box
// shares.
//
// Toyota's Home-screen box and Sydney's Agent Management page are the same
// desk: a Pause/Play gate on her own edge-tts voice (starting paused, so she
// never startles anyone), the Pipecat recorder when the server admits her to
// the voice pilot, a Start Listening button with its own continuous listener,
// the dark editable note, and the window hand-off ("bring up Mazda", "put
// Toyota on"). What differs between desks is an IReceptionistDesk descriptor;
// everything else lives here once, so a fix to one desk is a fix to both.
//
// A desk is long-lived: build it once per agent and ask it for renderer
// options on every render, so the gate, voice, listener and conversation
// survive navigating away and back (Sydney's page is rebuilt per open).

import {
  AgentWindowHandoff,
  BrowserAgentWindows,
  BrowserSpeechRecognitionListener,
  EdgeTtsSpeechSynthesizer,
  EditableDarkNoteSurface,
  PausableAudioGate,
  SpokenOutputPolicy,
  VoiceSession,
} from "../implementation/index.js";
import { recorderFactoryForAgent } from "./pipecat-voice-pilot.js";

/**
 * What differs between two receptionist desks.
 *
 * @typedef {object} IReceptionistDesk
 * @property {string} name             display name ("Toyota", "Sydney")
 * @property {string} agentId          her id in /api/agents
 * @property {string} boxId            element the box renders into
 * @property {object} conversationAgent the IConversationAgent behind the box,
 *                                     before the window hand-off wraps it
 * @property {{evaluate:(text:string)=>Promise<object>}} intentPolicy
 *                                     decides whether a heard phrase is for her
 * @property {boolean|(()=>boolean)} pipecatSelected
 *                                     whether the server put her on the Pipecat
 *                                     voice pilot; a function is asked per
 *                                     recording, for desks that learn it late
 */

export class ReceptionistDesk {
  /**
   * @param {IReceptionistDesk} desk
   * @param {object} deps
   */
  constructor(
    desk,
    {
      http,
      storage = globalThis.localStorage,
      doc = globalThis.document,
      win = globalThis.window,
      recorderFactoryBuilder = recorderFactoryForAgent,
      listenerFactory = () => new BrowserSpeechRecognitionListener(),
      playbackControl = new PausableAudioGate({ paused: true }),
      // Her own synthesizer, so the gate holds only her voice, not the other
      // agents' pages that share the dashboard's `speech`.
      speechFactory = (gate) =>
        new EdgeTtsSpeechSynthesizer(win, { audioFactory: gate.audioFactory }),
      speech = null,
    },
  ) {
    this._desk = desk;
    this._http = http;
    this._storage = storage;
    this._doc = doc;
    this.voiceSession = new VoiceSession();
    this.conversationAgent = new AgentWindowHandoff(
      desk.conversationAgent,
      new BrowserAgentWindows({ win, doc, boxId: desk.boxId }),
    );
    this.playbackControl = playbackControl;
    this._speech = playbackControl ? speechFactory(playbackControl) : speech;
    this._listener = listenerFactory();
    this._recorderFactory = recorderFactoryBuilder(desk.agentId, storage, {
      serverSelected: desk.pipecatSelected,
    });
  }

  /** Options for one InputOptionsRenderer render of this desk. */
  rendererOptions() {
    return {
      http: this._http,
      conversationAgent: this.conversationAgent,
      voiceSession: this.voiceSession,
      spokenOutputPolicy: new SpokenOutputPolicy({
        session: this.voiceSession,
      }),
      speech: this._speech,
      playbackControl: this.playbackControl,
      agentName: this._desk.name,
      agentId: this._desk.agentId,
      storage: this._storage,
      doc: this._doc,
      recorderFactory: this._recorderFactory,
      listener: this._listener,
      receptionistIntentPolicy: this._desk.intentPolicy,
      surfaceFactory: (opts) => new EditableDarkNoteSurface(opts),
    };
  }
}
