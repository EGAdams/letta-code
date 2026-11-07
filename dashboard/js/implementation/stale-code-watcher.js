/**
 * StaleCodeWatcher -- reloads a long-open dashboard tab once the code it is
 * running has changed on the server.
 *
 * A tab keeps the JavaScript and CSS it loaded at start-up, so a fix deployed
 * afterwards never reaches it until someone presses refresh. This watches the
 * very files the page loaded (`listUrls`, from the browser's resource
 * timing), compares each one's Last-Modified/Content-Length with what it was
 * when first seen, and calls `reload` when any differ.
 *
 * It never reloads out from under a person typing: `canReload()` is asked
 * first, and a refusal is simply retried on the next check. It also never
 * raises -- a failed request just means "no news".
 *
 * Every dependency is injected (fetch, the URL list, timers, reload), so the
 * tests drive it with scripted responders and no browser.
 */
export class StaleCodeWatcher {
  constructor({
    fetchFn,
    listUrls,
    canReload = () => true,
    reload,
    setInterval = globalThis.setInterval?.bind(globalThis),
    clearInterval = globalThis.clearInterval?.bind(globalThis),
    intervalMs = 15000,
    batchSize = 40,
    log = () => {},
  } = {}) {
    if (
      typeof fetchFn !== "function" ||
      typeof listUrls !== "function" ||
      typeof reload !== "function"
    ) {
      throw new Error("StaleCodeWatcher requires fetchFn, listUrls and reload");
    }
    Object.assign(this, {
      _fetch: fetchFn,
      _list: listUrls,
      _canReload: canReload,
      _reload: reload,
      _log: log,
    });
    this._setInterval = setInterval;
    this._clearInterval = clearInterval;
    this._intervalMs = intervalMs;
    this._batch = batchSize;
    this._seen = new Map(); // url -> signature when first seen
    this._cursor = 0;
    this._timer = null;
    this._stale = false;
    this._busy = false;
  }

  /** Records every file's current signature, then checks on a timer. */
  async start() {
    await this._check(Infinity);
    if (this._setInterval)
      this._timer = this._setInterval(() => this.check(), this._intervalMs);
  }

  stop() {
    if (this._timer !== null) this._clearInterval?.(this._timer);
    this._timer = null;
  }

  /** One round: the next few files, round-robin. Resolves true if a reload was requested. */
  check() {
    return this._check(this._batch);
  }

  async _check(limit) {
    if (this._busy) return false;
    this._busy = true;
    try {
      if (!this._stale) {
        const urls = this._list();
        const start = this._cursor % Math.max(urls.length, 1);
        const picked = Number.isFinite(limit)
          ? urls
              .slice(start, start + limit)
              .concat(urls.slice(0, Math.max(0, start + limit - urls.length)))
          : urls;
        this._cursor = start + picked.length;
        for (const url of new Set(picked)) {
          const signature = await this._signature(url);
          if (signature === null) continue;
          const first = this._seen.get(url);
          if (first === undefined) this._seen.set(url, signature);
          else if (first !== signature) {
            this._stale = true;
            this._log(`dashboard code changed: ${url}`);
            break;
          }
        }
      }
      if (this._stale && this._canReload()) {
        this._reload();
        return true;
      }
      return false;
    } catch (_) {
      return false;
    } finally {
      this._busy = false;
    }
  }

  async _signature(url) {
    try {
      const response = await this._fetch(url, {
        method: "HEAD",
        cache: "no-store",
      });
      if (!response.ok) return null;
      const modified = response.headers.get("last-modified") || "";
      const length = response.headers.get("content-length") || "";
      return modified || length ? `${modified}|${length}` : null;
    } catch (_) {
      return null;
    }
  }
}

/** Same-origin scripts/styles this page loaded, plus the page itself. */
export function loadedCodeUrls(
  perf = globalThis.performance,
  origin = globalThis.location?.origin,
) {
  const urls = new Set([`${origin}/`]);
  for (const entry of perf?.getEntriesByType?.("resource") || []) {
    let u;
    try {
      u = new URL(entry.name);
    } catch (_) {
      continue;
    }
    if (u.origin === origin && /\.(js|mjs|css)$/.test(u.pathname))
      urls.add(u.href);
  }
  return [...urls];
}

/** True while a person is typing into a field: never reload then. */
export function isTyping(doc = globalThis.document) {
  const el = doc?.activeElement;
  if (!el) return false;
  const tag = String(el.tagName || "").toLowerCase();
  return (
    tag === "textarea" ||
    tag === "input" ||
    tag === "select" ||
    el.isContentEditable === true
  );
}
