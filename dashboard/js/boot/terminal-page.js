// terminal-page.js — composition root for the Terminal tab. Loaded by its own
// <script type="module"> tag in dashboard.html (same pattern as
// all-monitors.js), not through dashboard-boot.js, so it has no dependency on
// that composition root's own nav wiring.
import { createTerminalFeed } from "../implementation/dom-terminal-feed.js";
import { FetchHttpClient } from "../implementation/fetch-http-client.js";

export function bootTerminalPage(doc = document, win = window) {
  const view = doc.getElementById("terminal");
  if (!view) return null;
  return createTerminalFeed({ doc, win, http: new FetchHttpClient() });
}

bootTerminalPage();
