// startup-gate.js — the progress overlay both boot-time gates share.
//
// The dashboard shows the same overlay twice: once while the server/SSH
// registries and health checks load (the "startup" gate) and once while the
// agent roster loads (the "agent" gate). They were two 135-line copies of the
// same code in dashboard-boot.js that differed only in their task list and
// four strings — a Template Method with the varying parts injected instead.
//
// No DOM lookups happen here: the caller passes the four elements and a doc /
// win, so this module is unit-testable against js/tests/_fake-dom.js.

const FILL_PHASE_MS = 2500;
const GREEN_PHASE_MS = 3000;
const FINISH_DELAY_MS = FILL_PHASE_MS + GREEN_PHASE_MS;
const LOG_SPACING_MS = 75;

/**
 * @param {object} opts
 * @param {Document} opts.doc
 * @param {Window} opts.win
 * @param {{overlay, statusText, progressBar, console}} opts.elements
 * @param {Array<{key: string, label: string, detail: string}>} opts.tasks
 * @param {{running: string, starting: string, advancing: string,
 *          finished: string, finishedLine: string}} opts.labels
 * @param {boolean} [opts.resettable] true if start() may run more than once
 *        (the agent gate reopens every time Agent Management is entered).
 */
export function createStartupGate({
  doc,
  win,
  elements,
  tasks,
  labels,
  resettable = false,
}) {
  const { overlay, statusText, progressBar, console: consoleEl } = elements;
  const completed = new Set();
  let released = false;
  let finishTimer = null;
  let greenTimer = null;
  let logChain = Promise.resolve();
  let hasLogged = false;

  function resetBar() {
    if (!progressBar) return;
    progressBar.style.transition = "none";
    progressBar.style.width = "0%";
    progressBar.offsetHeight;
    progressBar.style.transition = "";
  }

  function animateCompletionBar() {
    if (!progressBar) return;
    progressBar.style.transition = "none";
    progressBar.style.width = "0%";
    progressBar.offsetHeight;
    progressBar.style.transition = `width ${FILL_PHASE_MS}ms linear`;
    progressBar.style.width = "100%";
  }

  function renderProgress(currentLabel) {
    if (statusText) statusText.textContent = currentLabel;
  }

  function log(text, className = "") {
    if (!consoleEl) return;
    const line = doc.createElement("div");
    if (className) line.className = className;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
    return line;
  }

  // Log lines are spaced out so the console reads like a machine working
  // through a checklist rather than dumping everything in one frame.
  function writeLine(text, className = "") {
    const waitMs = hasLogged ? LOG_SPACING_MS : 0;
    hasLogged = true;
    logChain = logChain
      .then(
        () =>
          new Promise((resolve) => {
            win.setTimeout(resolve, waitMs);
          }),
      )
      .then(() => log(text, className));
    return logChain;
  }

  function advance(key, text) {
    const task = tasks.find((entry) => entry.key === key);
    completed.add(key);
    log(text || `${task?.label || key} complete.`);
    renderProgress(task?.detail || labels.advancing);
  }

  return {
    start() {
      doc.body.classList.add("startup-loading");
      if (resettable) overlay?.classList.remove("hidden");
      overlay?.classList.remove("startup-complete");
      if (finishTimer) win.clearTimeout(finishTimer);
      if (greenTimer) win.clearTimeout(greenTimer);
      finishTimer = null;
      greenTimer = null;
      logChain = Promise.resolve();
      hasLogged = false;
      if (resettable) {
        completed.clear();
        released = false;
        if (consoleEl) consoleEl.innerHTML = "";
      }
      resetBar();
      renderProgress(labels.running);
      writeLine(labels.starting);
    },
    complete(key, text) {
      if (released || completed.has(key)) return;
      advance(key, text);
      if (completed.size === tasks.length) this.finish();
    },
    fail(key, error) {
      if (released || completed.has(key)) return;
      const task = tasks.find((entry) => entry.key === key);
      advance(
        key,
        `${task?.label || key} failed: ${error?.message || error || "Unknown error"}`,
      );
      if (completed.size === tasks.length) this.finish();
    },
    writeLine(text, className = "") {
      return writeLine(text, className);
    },
    async finish() {
      if (released) return;
      released = true;
      renderProgress(labels.running);
      animateCompletionBar();
      greenTimer = win.setTimeout(() => {
        overlay?.classList.add("startup-complete");
        if (statusText) statusText.textContent = labels.finished;
        const finalLine = log(labels.finishedLine, "startup-final-line");
        finalLine?.classList.add("startup-blink");
      }, FILL_PHASE_MS);
      await new Promise((resolve) => {
        finishTimer = win.setTimeout(resolve, FINISH_DELAY_MS);
      });
      await logChain;
      doc.body.classList.remove("startup-loading");
      overlay?.classList.add("hidden");
    },
  };
}
