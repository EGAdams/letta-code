// agent-detail-renderers.js — the Strategy table behind AM.renderDetail().
//
// Maps an agent-detail view id to how its content is rendered. The three
// streams (Thoughts / Messages / Tool Calls) are long-lived StreamDetailRenderers
// sharing one ActivePoller; Chat and Input Options are rebuilt per open so they
// carry the current agent's name (heading + per-agent voice).

import {
  AgentCardRenderer,
  AgentsRouterRenderer,
  AgentWindowHandoff,
  BrowserAgentWindows,
  BrowserSpeechRecognitionListener,
  CASHY_AGENT_ID,
  ChatDetailRenderer,
  EditableDarkNoteSurface,
  InputOptionsRenderer,
  LettaAgentAdapter,
  MAZDA_AGENT_ID,
  SessionState,
  SpokenOutputPolicy,
  StreamDetailRenderer,
  StreamingLettaAgentAdapter,
  SYDNEY_AGENT_ID,
  TestChatAgentAdapter,
  VoiceSession,
  wakePhraseIntentPolicy,
} from "../implementation/index.js";
import { recorderFactoryForAgent } from "./pipecat-voice-pilot.js";
import { ReceptionistDesk } from "./receptionist-desk.js";

export function createAgentDetailRenderers({
  http,
  poller,
  speech,
  setAgentTabStatus,
  getAgentManager,
  storage = globalThis.localStorage,
  doc = globalThis.document,
  win = globalThis.window,
  deskFactory = (desk, deps) => new ReceptionistDesk(desk, deps),
}) {
  const streamRenderers = {
    "agent-detail-thoughts": new StreamDetailRenderer({
      http,
      poller,
      url: "/api/thoughts",
      label: "thoughts",
    }),
    "agent-detail-messages": new StreamDetailRenderer({
      http,
      poller,
      url: "/api/messages",
      label: "messages",
    }),
    "agent-detail-tool-calls": new StreamDetailRenderer({
      http,
      poller,
      url: "/api/toolcalls",
      label: "tool calls",
    }),
  };
  const agentCardRenderer = new AgentCardRenderer({ http });
  const voiceSessions = new Map();
  const conversationAgents = new Map();
  const chatSessions = new Map();
  const chatAgents = new Map();
  const sessionFor = (sessions, id) => {
    let session = sessions.get(id);
    if (!session || session.closed) {
      session = new VoiceSession();
      sessions.set(id, session);
    }
    return session;
  };
  const interruptSessions = (sessions, adapters) => {
    for (const [id, session] of sessions) {
      if (
        [SessionState.THINKING, SessionState.SPEAKING].includes(session.state)
      ) {
        if (session.state === SessionState.THINKING)
          adapters.get(id)?.cancel(session.currentGeneration);
        session.interrupt();
      }
    }
  };
  const interruptVoiceTurns = () => {
    interruptSessions(voiceSessions, conversationAgents);
    interruptSessions(chatSessions, chatAgents);
  };

  const renderChat = (am, target) => {
    const voiceSession = sessionFor(chatSessions, am.current.id);
    let conversationAgent = chatAgents.get(am.current.id);
    if (!conversationAgent) {
      conversationAgent = new TestChatAgentAdapter({ http });
      chatAgents.set(am.current.id, conversationAgent);
    }
    return new ChatDetailRenderer({
      conversationAgent,
      voiceSession,
      spokenOutputPolicy: new SpokenOutputPolicy({ session: voiceSession }),
      speech,
      agentName: am.current.name,
      agentId: am.current.id,
      onStatus: setAgentTabStatus,
      storage,
      doc,
    }).render(target, am.current.id);
  };

  // Mazda gets a box like Toyota's: streaming replies through
  // /api/mazda-turn (shared LanceDB recall + "put Toyota on the horn"), a
  // Start Listening button answering to "Mazda, ...", and the dark note
  // surface. Her listener outlives re-renders like the router's does.
  const listeners = new Map();
  const receptionistOptions = (name) => {
    if (!listeners.has(name))
      listeners.set(name, new BrowserSpeechRecognitionListener());
    return {
      listener: listeners.get(name),
      receptionistIntentPolicy: wakePhraseIntentPolicy(name),
      surfaceFactory: (opts) => new EditableDarkNoteSurface(opts),
    };
  };
  const RECEPTIONIST_BOXES = {
    [MAZDA_AGENT_ID]: { name: "mazda", endpoint: "/api/mazda-turn" },
  };

  // Sydney is not "a box like Toyota's": she IS Toyota's desk — the same
  // ReceptionistDesk Toyota's Home screen is built from, so the Pause gate,
  // her own voice, the Pipecat recorder and Start Listening come with it. Her
  // turns go to /api/sydney-turn (the sidecar run as --agent sydney), and
  // "Sydney, put Toyota on" opens the front desk through the same hand-off.
  // Whether she is on the voice pilot is the server's call, learned once;
  // until it answers she records on the default path.
  const DESKS = {
    [SYDNEY_AGENT_ID]: (target) => {
      let pipecat = false;
      http
        .getJSON(`/api/voice-media-backend?agent=${SYDNEY_AGENT_ID}`)
        .then((d) => {
          pipecat = d?.voice_media_backend === "pipecat";
        })
        .catch(() => {});
      return deskFactory(
        {
          name: "Sydney",
          agentId: SYDNEY_AGENT_ID,
          boxId: target,
          conversationAgent: new StreamingLettaAgentAdapter({
            storage,
            endpoint: "/api/sydney-turn",
          }),
          intentPolicy: wakePhraseIntentPolicy("sydney"),
          pipecatSelected: () => pipecat,
        },
        { http, storage, doc, win },
      );
    },
    // Cashy gets the same desk. She is not on the Pipecat voice pilot, so
    // she always records on the default path.
    [CASHY_AGENT_ID]: (target) =>
      deskFactory(
        {
          name: "Cashy",
          agentId: CASHY_AGENT_ID,
          boxId: target,
          conversationAgent: new StreamingLettaAgentAdapter({
            storage,
            endpoint: "/api/cashy-turn",
          }),
          intentPolicy: wakePhraseIntentPolicy("cashy"),
          pipecatSelected: () => false,
        },
        { http, storage, doc, win },
      ),
  };
  const desks = new Map();
  const deskFor = (id, target) => {
    if (!DESKS[id]) return null;
    if (!desks.has(id)) desks.set(id, DESKS[id](target));
    return desks.get(id);
  };
  const newConversationAgent = (id, target) =>
    RECEPTIONIST_BOXES[id]
      ? new AgentWindowHandoff(
          new StreamingLettaAgentAdapter({
            storage,
            endpoint: RECEPTIONIST_BOXES[id].endpoint,
          }),
          new BrowserAgentWindows({ win, doc, boxId: target }),
        )
      : new LettaAgentAdapter({ http, storage });

  const renderInputOptions = (am, target) => {
    const desk = deskFor(am.current.id, target);
    if (desk)
      return new InputOptionsRenderer({
        ...desk.rendererOptions(),
        onStatus: setAgentTabStatus,
      }).render(target, am.current.id);
    const voiceSession = sessionFor(voiceSessions, am.current.id);
    let conversationAgent = conversationAgents.get(am.current.id);
    if (!conversationAgent) {
      conversationAgent = newConversationAgent(am.current.id, target);
      conversationAgents.set(am.current.id, conversationAgent);
    }
    const box = RECEPTIONIST_BOXES[am.current.id];
    const receptionist = box ? receptionistOptions(box.name) : {};
    return new InputOptionsRenderer({
      ...receptionist,
      http,
      conversationAgent,
      voiceSession,
      spokenOutputPolicy: new SpokenOutputPolicy({ session: voiceSession }),
      speech,
      agentName: am.current.name,
      agentId: am.current.id,
      onStatus: setAgentTabStatus,
      storage,
      doc,
      recorderFactory: recorderFactoryForAgent(am.current.id, storage),
    }).render(target, am.current.id);
  };

  // Long-lived across renders/navigation (unlike the renderers above, which are
  // rebuilt fresh on every open) so "Start Listening" keeps listening straight
  // through the hand-off to a detected agent's Input Options page — only the
  // callbacks get re-claimed per render, via setCallbacks() inside
  // AgentsRouterRenderer. See continuous-listener.interface.js.
  const routerListener = new BrowserSpeechRecognitionListener();

  const resolveAgentIdByName = (name) => {
    const match = (getAgentManager().agents || []).find(
      (a) => a.name.toLowerCase() === String(name).toLowerCase(),
    );
    return match ? match.id : null;
  };

  // Opens the detected agent's Input Options page and hands back its render()
  // api (setText/appendText) so the router can transfer the remainder text.
  const renderAgentsRouter = (target) =>
    new AgentsRouterRenderer({
      http,
      listener: routerListener,
      resolveAgentId: resolveAgentIdByName,
      openAgent: (id) => getAgentManager().openById(id, "input-options"),
      onStatus: setAgentTabStatus,
    }).render(target);

  const detailRenderers = {
    "agent-detail-thoughts": (am, id) =>
      streamRenderers[id].render(id, am.current.id),
    "agent-detail-messages": (am, id) =>
      streamRenderers[id].render(id, am.current.id),
    "agent-detail-tool-calls": (am, id) =>
      streamRenderers[id].render(id, am.current.id),
    "agent-detail-agent-card": (am, id) =>
      agentCardRenderer.render(id, am.current.id),
    "agent-detail-tests": (am, id) => renderChat(am, id),
    "agent-detail-input-options": (am, id) => renderInputOptions(am, id),
  };

  return { detailRenderers, renderAgentsRouter, interruptVoiceTurns };
}
