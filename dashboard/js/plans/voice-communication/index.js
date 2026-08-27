import { audioCaptureSpec } from "./specs/audio-capture.js";
import { conversationAgentSpec } from "./specs/conversation-agent.js";
import { conversationCoordinatorSpec } from "./specs/conversation-coordinator.js";
import { designProtocolSpec } from "./specs/design-protocol.js";
import { detectionInterfaceSpec } from "./specs/detection-interface.js";
import { languageProcessorSpec } from "./specs/language-processor.js";
import { lettaAgentAdapterSpec } from "./specs/letta-agent-adapter.js";
import { noteCommandSpec } from "./specs/note-command-channel.js";
import { overviewSpec } from "./specs/overview.js";
import { routeStrategySpec } from "./specs/route-strategy.js";
import { speechSynthesisSpec } from "./specs/speech-synthesis.js";
import { spokenOutputPolicySpec } from "./specs/spoken-output-policy.js";
import { transcriptionSpec } from "./specs/transcription.js";
import { voiceSessionSpec } from "./specs/voice-session.js";

/**
 * The Voice Communication workspace, in nav order.
 *
 * One file per tab under specs/, so adding an interface is a new file plus one
 * line here — never a change to the renderer, the shell, or any markup.
 *
 * Grouped by how real the code is, because that is the question you actually
 * arrive with: what can I rely on, what is half-built, what is still a plan.
 */
export const voiceCommunicationSpecs = [
  overviewSpec,

  // Named in the original plan. The browser-side core now exists and is
  // tested; what is still missing is a caller, not the objects.
  voiceSessionSpec,
  conversationAgentSpec,
  spokenOutputPolicySpec,
  conversationCoordinatorSpec,
  lettaAgentAdapterSpec,

  // Real, tested seams that carry the system today.
  audioCaptureSpec,
  transcriptionSpec,
  routeStrategySpec,
  speechSynthesisSpec,
  noteCommandSpec,

  // The prototype's interfaces, kept as history.
  detectionInterfaceSpec,
  languageProcessorSpec,

  designProtocolSpec,
];
