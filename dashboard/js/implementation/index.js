/**
 * implementation/ barrel — concrete subclasses that bind each abstract
 * interface in ../abstract/ to a real browser API. Import these from
 * dashboard.html (or a bundler entry) to replace the inline AM/SM logic.
 */

export {
  AgentVoiceCatalog,
  DEFAULT_AGENT_VOICE_PREFERENCES,
  FEMALE_VOICE_RE,
  MALE_VOICE_RE,
} from "../abstract/agent-voice-catalog.interface.js";
export { ActivePoller } from "./active-poller.js";
export { AgentActivityPoller } from "./agent-activity-poller.js";
export { AgentStreamController } from "./agent-stream-controller.js";
export { BrowserSpeechSynthesizer } from "./browser-speech-synthesizer.js";
export {
  AgentCardRenderer,
  ChatDetailRenderer,
  composeSpokenText,
  InputOptionsRenderer,
  renderReplyRows,
  StreamDetailRenderer,
} from "./detail-renderers.js";
export { DomConsoleView } from "./dom-console-view.js";
export { DomNavigationController } from "./dom-navigation-controller.js";
export { DomTabFactory } from "./dom-tab-factory.js";
export { FetchHttpClient } from "./fetch-http-client.js";
export { MediaRecorderVoiceRecorder } from "./media-recorder-voice-recorder.js";
export {
  buildServerActionRequest,
  ServerActionController,
} from "./server-action-controller.js";
export { ServerHealthMonitor } from "./server-health-monitor.js";
export {
  classifyServerStatus,
  ServerLogController,
} from "./server-log-controller.js";
