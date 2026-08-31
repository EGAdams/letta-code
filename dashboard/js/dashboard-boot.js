// dashboard-boot.js — the dashboard's composition root.
//
// This is the thin boot layer that wires the GoF library in js/implementation/
// to the live page. It constructs the shared ports (HttpClient, ActivePoller,
// DomTabFactory, SpeechSynthesizer), builds each section's controller from
// js/boot/, and hands them to the navigation bindings. No behaviour lives
// here: every section is its own module under js/boot/, every reusable class
// lives under js/implementation/, and every pure rule lives under
// js/abstract/ where it can be unit-tested without a browser.
//
// Construction order matters and is the only reason this file reads
// top-to-bottom: view navigation is needed by every section, the sections are
// needed by the nav bindings, and the nav bindings must exist before the
// deep-link runs.

import { createAgentManager } from "./boot/agent-manager.js";
import { createAgentTabStatus } from "./boot/agent-tab-status.js";
import { bindNavigation } from "./boot/bindings/index.js";
import { applyDeepLink } from "./boot/deep-link.js";
import { createGates } from "./boot/gates.js";
import { createModelStats } from "./boot/model-stats.js";
import {
  collectNavElements,
  collectStartupElements,
} from "./boot/nav-elements.js";
import { createPcMonitor } from "./boot/pc-monitor.js";
import { startReceptionist } from "./boot/receptionist.js";
import { createRolFinance } from "./boot/rol-finance.js";
import { setupScanners } from "./boot/scanners/index.js";
import { createServerManager } from "./boot/server-manager.js";
import { createSshManager } from "./boot/ssh-manager.js";
import { createStartupChecks } from "./boot/startup-checks.js";
import { createViewNavigator } from "./boot/view-navigator.js";
import {
  ActivePoller,
  CodeChangeAlert,
  DomChatGptProviderAccountController,
  DomTabFactory,
  EdgeTtsSpeechSynthesizer,
  FetchHttpClient,
  IntakeHaltAlert,
  PrinterRepairController,
  VisionHaltAlert,
} from "./implementation/index.js";
import { VoiceCommunicationNavigationController } from "./implementation/voice-communication-navigation-controller.js";
import { voiceCommunicationSpecs } from "./plans/voice-communication/index.js";

const doc = document;
const win = window;

/* ─────────────────────────  Shared ports  ───────────────────────── */

// One HttpClient (Adapter over fetch) shared by AM / SM / SSHM / RF.
const http = new FetchHttpClient();
// One ActivePoller: only one agent stream polls at a time, so switching
// tabs/agents stops the previous stream before starting a new one.
const poller = new ActivePoller();
// Builds sidebar agent/server/connection tabs with the right dataset+classes.
const tabFactory = new DomTabFactory();
const printerRepair = new PrinterRepairController({ http });
// The agents speak with the same edge-tts en-GB-SoniaNeural voice the
// pickle_cpp scoreboard uses: EdgeTtsSpeechSynthesizer (Decorator over the
// BrowserSpeechSynthesizer facade) POSTs the reply text to /api/tts and plays
// the returned MP3. It intentionally stays silent if server audio is
// unavailable, so a browser-local robotic voice cannot replace an agent's
// configured voice.
const speech = new EdgeTtsSpeechSynthesizer(win);

const nav = collectNavElements(doc);
const { startupGate, agentGate } = createGates({
  doc,
  win,
  elements: collectStartupElements(doc),
});
const viewNav = createViewNavigator({ doc, nav });
viewNav.setAgentDetailContent("Agent");

/* ─────────────────────────  Sections  ───────────────────────── */

const voiceCommunicationNav = new VoiceCommunicationNavigationController({
  plansNav: nav.plans,
  voiceNav: nav.voiceCommunication,
  frame: doc.getElementById("voice-communication-plan-frame"),
  specs: voiceCommunicationSpecs,
  activateView: viewNav.activateView,
  setActive: viewNav.setActive,
  doc,
});
voiceCommunicationNav.bind();

const agentTabStatus = createAgentTabStatus({ doc, http, nav });
const AM = createAgentManager({
  doc,
  http,
  poller,
  nav,
  viewNav,
  agentGate,
  tabFactory,
  speech,
  setAgentTabStatus: agentTabStatus.setAgentTabStatus,
});
const MS = createModelStats({ doc, http, nav, viewNav });
const providerAccountMonitor = new DomChatGptProviderAccountController({
  http,
  doc,
});
providerAccountMonitor.mount("chatgpt-provider-account-panel");
const PCM = createPcMonitor({ doc, http, nav, viewNav });
const SM = createServerManager({ doc, http, nav, viewNav, tabFactory });
const SSHM = createSshManager({ doc, http, nav, viewNav, tabFactory });
const RF = createRolFinance({ doc, http, nav, viewNav });
const scanners = setupScanners({
  doc,
  win,
  http,
  printerRepair,
  AM,
  viewNav,
});

bindNavigation({
  doc,
  http,
  nav,
  viewNav,
  voiceCommunicationNav,
  AM,
  SM,
  SSHM,
  MS,
  PCM,
  RF,
  scanners,
});

/* ─────────────────────────  Background watchers  ───────────────────────── */

// Sidebar agent tab colours: activity every 5s, structural health every 30s.
agentTabStatus.start();
// Blink the Agents tab + prompt to restart when the dashboard's own source
// changes on disk (polls /api/code-status every 15s).
new CodeChangeAlert({ http }).start();
// Full-screen modal + red Window/Freezer scanner tabs when classify_scan.py's
// 3-tier vision fallback (Gemini -> ChatGPT-OAuth/Codex CLI -> OpenAI key) is
// ALL down (polls /api/server-health's 'document-vision' entry every 20s).
// Mirrors the server-side halt in process_scanned_document().
new VisionHaltAlert({ http }).start();
new IntakeHaltAlert({ http }).start();

/* ─────────────────────────  Go  ───────────────────────── */

startReceptionist({ http, speech });
applyDeepLink({ nav, AM, RF });
void createStartupChecks({
  doc,
  http,
  nav,
  tabFactory,
  startupGate,
  SM,
  SSHM,
})();
