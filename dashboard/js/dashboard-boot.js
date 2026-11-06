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

import { createAgentBridgePoll } from "./boot/agent-bridge-poll.js";
import { createAgentManager } from "./boot/agent-manager.js";
import { createAgentTabStatus } from "./boot/agent-tab-status.js";
import { bindNavigation } from "./boot/bindings/index.js";
import { createDashboardVersion } from "./boot/dashboard-version.js";
import { applyDeepLink } from "./boot/deep-link.js";
import { createGates } from "./boot/gates.js";
import { createModelStats } from "./boot/model-stats.js";
import {
  collectNavElements,
  collectStartupElements,
} from "./boot/nav-elements.js";
import { createNotes } from "./boot/notes.js";
import { createPcMonitor } from "./boot/pc-monitor.js";
import { createPrinterPanel } from "./boot/printer-panel.js";
import { startReceptionist } from "./boot/receptionist.js";
import { createRolFinance } from "./boot/rol-finance.js";
import { setupScanners } from "./boot/scanners/index.js";
import { createServerManager } from "./boot/server-manager.js";
import { createSshManager } from "./boot/ssh-manager.js";
import { createStartupChecks } from "./boot/startup-checks.js";
import { createStatusHome } from "./boot/status-home.js";
import { createViewNavigator } from "./boot/view-navigator.js";
import { createWorkerActivity } from "./boot/worker-activity.js";
import { createWslInterop } from "./boot/wsl-interop.js";
import { BrowserSpeechRecognitionListener } from "./implementation/browser-speech-recognition-listener.js";
import { HandsFreeNotesController } from "./implementation/hands-free-notes-controller.js";
import {
  ActivePoller,
  AdwPromptDialog,
  CodeChangeAlert,
  DomChatGptProviderAccountController,
  DomTabFactory,
  EdgeTtsSpeechSynthesizer,
  FetchHttpClient,
  IntakeHaltAlert,
  PrinterRepairController,
  ReceptionistFailureAlert,
  VisionHaltAlert,
  XtermTerminalLauncher,
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
const terminalLauncher = new XtermTerminalLauncher();
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
const notes = createNotes({ doc, http });
const _notesHandsFree = new HandsFreeNotesController({
  listener: new BrowserSpeechRecognitionListener({ window: win }),
  textarea: notes.textarea,
  status: notes.status,
  toggleButton: doc.getElementById("notes-hands-free"),
  onButton: doc.getElementById("notes-toyota-on"),
  offButton: doc.getElementById("notes-toyota-off"),
  recordButton: doc.getElementById("notes-record"),
  stopButton: doc.getElementById("notes-stop-recording"),
  openNew: notes.openNew,
  setName: notes.setName,
  save: notes.save,
  read: notes.read,
}).bind();
void http
  .getJSON(`/api/dashboard-config?_read=${Date.now()}`)
  .then((config) => {
    const address = doc.getElementById("mailing-address-value");
    if (address)
      address.textContent =
        config.mailing_address ||
        config.mailing_city_state ||
        "Grand Rapids, MI";
  })
  .catch(() => {});
// Re-read the directory whenever Notes is opened so changes made elsewhere
// become visible without requiring a full page reload.
doc
  .querySelector('[data-nav="main"][data-target="notes"]')
  ?.addEventListener("click", () => {
    void notes?.load?.();
  });
doc
  .getElementById("dashboard-notes-overview")
  ?.addEventListener("click", () => {
    viewNav.clearActive(nav.main, '[data-nav="main"][data-target]');
    viewNav.activateView("home");
  });

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
  terminalLauncher,
  setAgentTabStatus: agentTabStatus.setAgentTabStatus,
});
const MS = createModelStats({ doc, http, nav, viewNav });
const providerAccountMonitor = new DomChatGptProviderAccountController({
  http,
  doc,
});
providerAccountMonitor.mount("chatgpt-provider-account-panel");
const PCM = createPcMonitor({ doc, http, nav, viewNav });
const WI = createWslInterop({ doc, http, viewNav });
const WKR = createWorkerActivity({ doc, win, http });
createDashboardVersion({ doc });
const ABP = createAgentBridgePoll({ doc, win, http, workerFeed: WKR });
const PRN = createPrinterPanel({ doc, win, http });
const SM = createServerManager({ doc, http, nav, viewNav, tabFactory });
const statusHome = createStatusHome({ doc, http });
statusHome.bind();
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
  WI,
  ABP,
  PRN,
  WKR,
  RF,
  scanners,
  statusHome,
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
// A task Toyota or Sydney sent another agent that FAILED (polls
// /api/receptionist-alerts every 10s): red card, spoken once, notified.
new ReceptionistFailureAlert({ http, speech }).start();
// Yes/No questions an agent_blocks ADW is waiting on (polls /api/adw-prompt
// every 5s); the answer is POSTed back for the ADW to act on.
new AdwPromptDialog({ http }).start();

/* ─────────────────────────  Go  ───────────────────────── */

startReceptionist({ http, speech });
applyDeepLink({ nav, AM, RF });
// Every browser page load starts at Toyota, regardless of stale route state.
viewNav.resetForPageLoad();
void createStartupChecks({
  doc,
  http,
  nav,
  tabFactory,
  startupGate,
  SM,
  SSHM,
})();
