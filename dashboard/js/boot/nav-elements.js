// nav-elements.js — every sidebar/nav element the boot layer binds to.
//
// One lookup point instead of eighteen scattered `getElementById` consts, so
// the modules under js/boot/ receive a `nav` object rather than reaching into
// the document themselves.

export function collectNavElements(doc = document) {
  return {
    mainContent: doc.getElementById("main-content"),
    main: doc.getElementById("nav-main"),
    status: doc.getElementById("nav-status"),
    agents: doc.getElementById("nav-agents"),
    agentDetail: doc.getElementById("nav-agent-detail"),
    servers: doc.getElementById("nav-servers"),
    ssh: doc.getElementById("nav-ssh-connections"),
    plans: doc.getElementById("nav-plans"),
    agentBlocks: doc.getElementById("nav-agent-blocks"),
    processFlows: doc.getElementById("nav-process-flows"),
    voiceCommunication: doc.getElementById("nav-voice-communication"),
    rolFinance: doc.getElementById("nav-rol-finance"),
    rolFinanceReports: doc.getElementById("nav-rol-finance-reports"),
    scanners: doc.getElementById("nav-scanners"),
    modelStats: doc.getElementById("nav-model-stats"),
    pcMonitor: doc.getElementById("nav-pc-monitor"),
  };
}

export function collectStartupElements(doc = document) {
  return {
    overlay: doc.getElementById("startup-overlay"),
    statusText: doc.getElementById("startup-status-text"),
    progressBar: doc.getElementById("startup-progress-bar"),
    console: doc.getElementById("startup-console"),
  };
}
