// wsl-interop.js — the WSLInterop Entry tab under System Status.
//
// Polls /api/wsl-interop every 30s from boot, whether or not the page is open,
// because the whole point is to see the entry go missing before something
// tries to launch a Windows .exe. The tab is green when every WSL box has the
// entry, yellow when a box could not be asked, and blinking red when one has
// lost it. The page itself (cards + instructions) comes from
// js/abstract/wsl-interop-render.js.

import { TextUtils } from "../abstract/text-utils.js";
import { renderWslInterop } from "../abstract/wsl-interop-render.js";

const esc = TextUtils.esc;

const POLL_MS = 30000;

export function createWslInterop({ doc = document, http, viewNav }) {
  const tab = doc.getElementById("btn-wsl-interop");
  const body = doc.getElementById("wsl-interop-body");

  const WI = {
    last: null,
    paintTab(level) {
      if (!tab) return;
      tab.classList.remove("server-up", "server-concern", "server-down");
      tab.classList.add(
        level === "crit"
          ? "server-down"
          : level === "warn"
            ? "server-concern"
            : "server-up",
      );
      tab.classList.toggle("tab-alert", level === "warn");
      tab.classList.toggle("tab-alert-red", level === "crit");
      viewNav.updateSystemStatusTab();
    },
    async poll() {
      try {
        const d = await http.getJSON("/api/wsl-interop");
        this.last = d;
        this.paintTab(d.level);
        if (body && body.dataset.open === "1")
          body.innerHTML = renderWslInterop(d);
      } catch (e) {
        // The dashboard itself not answering is not evidence about the entry;
        // leave the colour alone and say so only if the page is open.
        if (body && body.dataset.open === "1" && !this.last) {
          body.innerHTML = `<p class="am-warn">Failed to load: ${esc(e.message)}</p>`;
        }
      }
    },
    open() {
      if (!body) return;
      body.dataset.open = "1";
      body.innerHTML = this.last
        ? renderWslInterop(this.last)
        : '<p class="am-dim">Checking&hellip;</p>';
      void this.poll();
    },
  };

  void WI.poll();
  setInterval(() => void WI.poll(), POLL_MS);
  return WI;
}
