// agent-detail-renderers.js — the Strategy table behind AM.renderDetail().
//
// Maps an agent-detail view id to how its content is rendered. The three
// streams (Thoughts / Messages / Tool Calls) are long-lived StreamDetailRenderers
// sharing one ActivePoller; Chat and Input Options are rebuilt per open so they
// carry the current agent's name (heading + per-agent voice).

import {
  AgentCardRenderer,
  AgentsRouterRenderer,
  BrowserSpeechRecognitionListener,
  ChatDetailRenderer,
  InputOptionsRenderer,
  LettaAgentAdapter,
  SessionState,
  SpokenOutputPolicy,
  StreamDetailRenderer,
  VoiceSession,
} from "../implementation/index.js";

export function createAgentDetailRenderers({
  http,
  poller,
  speech,
  setAgentTabStatus,
  getAgentManager,
  storage = globalThis.localStorage,
  doc = globalThis.document,
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
  const sessionFor = (id) => {
    let session = voiceSessions.get(id);
    if (!session || session.closed) {
      session = new VoiceSession();
      voiceSessions.set(id, session);
    }
    return session;
  };
  const interruptInputOptions = () => {
    for (const [id, session] of voiceSessions) {
      if (
        [SessionState.THINKING, SessionState.SPEAKING].includes(session.state)
      ) {
        if (session.state === SessionState.THINKING)
          conversationAgents.get(id)?.cancel(session.currentGeneration);
        session.interrupt();
      }
    }
  };

  const renderChat = (am, target) =>
    new ChatDetailRenderer({
      http,
      speech,
      agentName: am.current.name,
      agentId: am.current.id,
      onStatus: setAgentTabStatus,
    }).render(target, am.current.id);

  const renderInputOptions = (am, target) => {
    const voiceSession = sessionFor(am.current.id);
    let conversationAgent = conversationAgents.get(am.current.id);
    if (!conversationAgent) {
      conversationAgent = new LettaAgentAdapter({ http, storage });
      conversationAgents.set(am.current.id, conversationAgent);
    }
    return new InputOptionsRenderer({
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

  return { detailRenderers, renderAgentsRouter, interruptInputOptions };
}
