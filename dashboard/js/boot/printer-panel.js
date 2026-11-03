// printer-panel.js — the Printer tab under System Status.
//
// Asks /api/printer every 30 s (the server caches Windows' answer for as long),
// so the tab is green when printing is switched on and a default printer
// answered. While a job is open it asks every 5 s. "Print the test page" asks
// the browser to confirm first and sends {confirm: true}; the server prints
// only its own fixed test page, so nothing typed here can reach paper.

import {
  canCancel,
  renderPrinterPage,
  tabClassFor,
} from "../abstract/printer-render.js";

const SLOW_MS = 30000;
const FAST_MS = 5000;
const URL = "/api/printer";

export function createPrinterPanel({ doc = document, win = window, http }) {
  const tab = doc.getElementById("btn-printer");
  const body = doc.getElementById("printer-body");

  const PRN = {
    last: null,
    ui: {},
    timer: null,
    isOpen() {
      return body?.dataset.open === "1";
    },
    render() {
      if (body && this.isOpen())
        body.innerHTML = renderPrinterPage(this.last, this.ui);
    },
    paintTab() {
      if (!tab) return;
      tab.classList.remove("server-up", "poll-disabled");
      tab.classList.add(tabClassFor(this.last));
    },
    schedule() {
      win.clearTimeout(this.timer);
      const busy = (this.last?.recent || []).some(canCancel) || this.ui.busy;
      this.timer = win.setTimeout(
        () => void this.poll(busy),
        busy ? FAST_MS : SLOW_MS,
      );
    },
    async poll(refresh = false) {
      try {
        this.last = await http.getJSON(refresh ? `${URL}?refresh=1` : URL, {
          timeout: 150000,
        });
      } catch (e) {
        this.last = {
          ok: false,
          enabled: false,
          error: e.message,
          printers: [],
          recent: [],
          documents: 0,
        };
      }
      if (this.ui.busy && !(this.last.recent || []).some(canCancel))
        this.ui.busy = false;
      this.paintTab();
      this.render();
      this.schedule();
    },
    async testPrint() {
      if (
        !win.confirm(
          "Print one STAR TREK BRIDGE test page on the default printer?",
        )
      )
        return;
      this.ui = { busy: true };
      this.render();
      let answer;
      try {
        answer = await http.postJSON(
          `${URL}/test-print`,
          { confirm: true },
          { timeout: 30000 },
        );
      } catch (e) {
        answer = { ok: false, message: `Not sent: ${e.message}` };
      }
      this.ui = { busy: !!answer.ok, ok: !!answer.ok, message: answer.message };
      win.setTimeout(() => void this.poll(true), 3000);
      this.render();
    },
    async cancel(jobId) {
      if (!win.confirm(`Cancel print job ${jobId}?`)) return;
      let answer;
      try {
        answer = await http.postJSON(
          `${URL}/cancel`,
          { job_id: jobId },
          { timeout: 150000 },
        );
      } catch (e) {
        answer = { ok: false, message: `Cancel failed: ${e.message}` };
      }
      this.ui = { ok: !!answer.ok, message: answer.message };
      await this.poll(true);
    },
    open() {
      if (!body) return;
      body.dataset.open = "1";
      this.render();
      void this.poll(true);
    },
  };

  body?.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-prn]");
    if (!button) return;
    const action = button.dataset.prn;
    if (action === "refresh") void PRN.poll(true);
    if (action === "test" && !PRN.ui.busy) void PRN.testPrint();
    if (action === "cancel") void PRN.cancel(button.dataset.job);
  });

  void PRN.poll();
  return PRN;
}
