// agent-window-handoff.js — "Toyota, bring up Mazda" / "Mazda, put Toyota on
// the horn".
//
// Both brains announce a hand-off the same way: a `tool_result` named
// `agent_handoff` whose detail is `{handoff: {agent, name}}` (Toyota's comes
// from the receptionist_team sidecar, Mazda's from /api/mazda-turn). Neither
// brain knows about browser windows, and the renderer below them should not
// learn about agents' windows either, so the reaction lives in one Decorator
// on the ConversationAgent port: every event passes through untouched, and a
// hand-off event additionally asks an AgentWindows to show that agent.
//
// Opening a window from a voice turn is not a user gesture, so Chrome may
// block it. BrowserAgentWindows then leaves a button in the agent's box — one
// click opens the same window.

import {
  AgentEventKind,
  ConversationAgent,
} from "../abstract/conversation-agent.interface.js";

/** Mazda's Letta id — keep in step with mazda_service.MAZDA_AGENT_ID. */
export const MAZDA_AGENT_ID = "agent-6b536cf4-ec88-4290-b595-fed21d14bd8e";

/**
 * Sydney's id in /api/agents — keep in step with sydney_service.SYDNEY_AGENT_ID.
 * Not a Letta id: she is Toyota's receptionist_team engine run as --agent
 * sydney, so her turns go to /api/sydney-turn.
 */
export const SYDNEY_AGENT_ID = "agent-sydney";

/** The Home screen's window name, so Mazda can find her way back to it. */
export const FRONT_DESK_WINDOW = "rol-front-desk";

/** Where each hand-off target lives. Unknown agents are ignored, not guessed. */
export const AGENT_WINDOWS = Object.freeze({
  mazda: {
    url: `/?agent=${MAZDA_AGENT_ID}&view=input-options`,
    windowName: "rol-agent-mazda",
  },
  sydney: {
    url: `/?agent=${SYDNEY_AGENT_ID}&view=input-options`,
    windowName: "rol-agent-sydney",
  },
  toyota: { url: "/", windowName: FRONT_DESK_WINDOW },
});

/** Decorator: passes every event through; shows the agent a hand-off names. */
export class AgentWindowHandoff extends ConversationAgent {
  constructor(inner, windows) {
    super();
    this._inner = inner;
    this._windows = windows;
  }

  async *submit(turn, generationId) {
    for await (const event of this._inner.submit(turn, generationId)) {
      if (
        event.kind === AgentEventKind.TOOL_RESULT &&
        event.name === "agent_handoff"
      ) {
        try {
          this._windows.show(event.detail?.handoff);
        } catch {}
      }
      yield event;
    }
  }

  cancel(generationId) {
    this._inner.cancel(generationId);
  }

  // Boot code and tests read the endpoint off the agent they were handed.
  get endpoint() {
    return this._inner.endpoint;
  }
}

/** Opens or focuses an agent's window, never reloading one already open. */
export class BrowserAgentWindows {
  constructor({
    win = globalThis.window,
    doc = globalThis.document,
    boxId,
    windows = AGENT_WINDOWS,
  }) {
    this._win = win;
    this._doc = doc;
    this._boxId = boxId;
    this._windows = windows;
  }

  show(handoff) {
    const target = this._windows[handoff?.agent];
    if (!target) return;
    if (this._focusOpener(target)) return;
    if (!this._open(target)) this._offerButton(target, handoff.name);
  }

  // Mazda's window was opened by the front desk; going back is a focus().
  _focusOpener(target) {
    const opener = this._win.opener;
    try {
      if (!opener || opener.closed || opener.name !== target.windowName)
        return false;
      opener.focus();
      return true;
    } catch {
      return false;
    }
  }

  // open("", name) returns an existing window without navigating it; only a
  // fresh about:blank one is pointed at the agent's page.
  _open(target) {
    let opened;
    try {
      opened = this._win.open("", target.windowName);
    } catch {
      return false;
    }
    if (!opened) return false;
    try {
      if (opened.location.href === "about:blank")
        opened.location.href = target.url;
    } catch {}
    try {
      opened.focus();
    } catch {}
    return true;
  }

  _offerButton(target, name) {
    const box = this._doc.getElementById(this._boxId);
    if (!box) return;
    const button = this._doc.createElement("button");
    button.type = "button";
    button.textContent = `Open ${name || "agent"}'s window`;
    button.addEventListener("click", () => {
      this._win.open(target.url, target.windowName);
      button.remove();
    });
    box.appendChild(button);
  }
}

/**
 * The browser-side wake phrase for an agent's own box, mirroring the server's
 * DeterministicReceptionistIntentStrategy for Toyota: "Mazda, ..." is
 * addressed to her; anything else is just transcript.
 */
export function wakePhraseIntentPolicy(name) {
  const pattern = new RegExp(
    `^\\s*(?:(?:hey|hi|hello|ok|okay)\\b[\\s,.:;!?-]*)?${name}\\b[\\s,.:;!?-]*(.+?)\\s*$`,
    "i",
  );
  return {
    evaluate: async (text) => {
      const request =
        typeof text === "string" ? (text.match(pattern)?.[1] ?? "").trim() : "";
      return request
        ? { addressed: true, cleaned_text: request }
        : { addressed: false, cleaned_text: "" };
    },
  };
}
