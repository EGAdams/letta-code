// auto-reload.js -- composition root for the stale-tab reload. Names the
// concretes: window.fetch, resource timing, location.reload.
import {
  isTyping,
  loadedCodeUrls,
  StaleCodeWatcher,
} from "../implementation/stale-code-watcher.js";

export function bootAutoReload(win = globalThis) {
  if (!win.document || !win.location || typeof win.fetch !== "function")
    return null;
  const watcher = new StaleCodeWatcher({
    fetchFn: win.fetch.bind(win),
    listUrls: () => loadedCodeUrls(win.performance, win.location.origin),
    canReload: () => !isTyping(win.document),
    reload: () => win.location.reload(),
  });
  // Wait for the page's own modules to finish loading so they are all in the list.
  const begin = () => win.setTimeout(() => watcher.start(), 4000);
  if (win.document.readyState === "complete") begin();
  else win.addEventListener("load", begin, { once: true });
  return watcher;
}

bootAutoReload();
