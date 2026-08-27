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
export {
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  isSpeakable,
  parseAgentEvent,
  SPEAKABLE_KINDS,
  TurnCancelledError,
} from "../abstract/conversation-agent.interface.js";
export {
  parseCompletenessDecision,
  parseNoteCommandOutcome,
} from "../abstract/note-command-contracts.js";
export { NoteDocument } from "../abstract/note-document.interface.js";
export { ReceptionistTranscriptController } from "../abstract/receptionist-transcript-controller.js";
export {
  Clock,
  IdSource,
  ManualClock,
  SequentialIdSource,
} from "../abstract/session-clock.js";
export {
  RejectionReason,
  SpokenOutputPolicy,
} from "../abstract/spoken-output-policy.js";
export { TranscriptBuffer } from "../abstract/transcript-buffer.js";
export { VoiceCommandChannel } from "../abstract/voice-command-channel.js";
export {
  IllegalTransitionError,
  SessionState,
  VoiceSession,
} from "../abstract/voice-session.js";
export { ActivePoller } from "./active-poller.js";
export { AgentActivityPoller } from "./agent-activity-poller.js";
export {
  AgentAssignmentsController,
  buildClaudeSdkAccountSelect,
  buildOauthAccountSelect,
} from "./agent-assignments-panel.js";
export { AgentHealthPoller } from "./agent-health-poller.js";
export { AgentStreamController } from "./agent-stream-controller.js";
export { AgentsRouterRenderer } from "./agents-router-renderer.js";
export { BrowserSpeechRecognitionListener } from "./browser-speech-recognition-listener.js";
export { BrowserSpeechSynthesizer } from "./browser-speech-synthesizer.js";
export { DomChatGptProviderAccountController } from "./chatgpt-provider-account-panel.js";
export { CodeChangeAlert } from "./code-change-alert.js";
export { DomCodexSyncController } from "./codex-sync-panel.js";
export {
  ConnectionLogController,
  ConnectionTestController,
  classifyConnectionStatus,
} from "./connection-controllers.js";
export { DashboardStatementReviewActions } from "./dashboard-statement-review-actions.js";
export {
  AgentCardRenderer,
  buildModelRow,
  ChatDetailRenderer,
  composeSpokenText,
  InputOptionsRenderer,
  mountTerminal,
  renderReplyRows,
  StreamDetailRenderer,
} from "./detail-renderers.js";
export {
  buildProcessDocumentRequest,
  buildProcessPdfRequest,
  DocumentPipelineController,
  describePipelineStage,
  summarizeParsed,
} from "./document-pipeline-controller.js";
export { DomConsoleView } from "./dom-console-view.js";
export { DomDocumentPipelineView } from "./dom-document-pipeline-view.js";
export { DomNavigationController } from "./dom-navigation-controller.js";
export { DomTabFactory } from "./dom-tab-factory.js";
export { DomVendorReviewView } from "./dom-vendor-review-view.js";
export { EdgeTtsSpeechSynthesizer } from "./edge-tts-speech-synthesizer.js";
export { FakeConversationAgent } from "./fake-conversation-agent.js";
export { FetchHttpClient } from "./fetch-http-client.js";
export {
  HttpCompletenessDetector,
  HttpNoteCommandInterpreter,
} from "./http-note-command-services.js";
export { IntakeHaltAlert } from "./intake-halt-alert.js";
export {
  LETTA_TURN_TIMEOUT_MS,
  LettaAgentAdapter,
} from "./letta-agent-adapter.js";
export { MediaRecorderVoiceRecorder } from "./media-recorder-voice-recorder.js";
export { ModelStatsHealthMonitor } from "./model-stats-health-monitor.js";
export { NoteCommandPanelRenderer } from "./note-command-panel.js";
export {
  buildPrinterRepairRequest,
  PrinterRepairController,
} from "./printer-repair-controller.js";
export { RolFinanceReportsController } from "./rol-finance-reports-controller.js";
export { ScannerDiagnosticsController } from "./scanner-diagnostics-controller.js";
export {
  buildServerActionRequest,
  ServerActionController,
} from "./server-action-controller.js";
export { ServerHealthMonitor } from "./server-health-monitor.js";
export {
  classifyServerStatus,
  ServerLogController,
} from "./server-log-controller.js";
export { StatementReviewDialog } from "./statement-review-dialog.js";
export {
  RandomIdSource,
  SystemClock,
} from "./system-session-primitives.js";
export {
  EditableTextareaSurface,
  ReadOnlyNoteSurface,
} from "./textarea-note-surfaces.js";
export { TranscriptSyncedNote } from "./transcript-synced-note.js";
export { VendorReviewController } from "./vendor-review-controller.js";
export { VisionHaltAlert } from "./vision-halt-alert.js";
