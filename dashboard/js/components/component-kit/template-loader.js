/**
 * TemplateLoader — stands in for the-factory's `import html from './x.html'`.
 * Fetches each component's HTML once and caches the promise; styles go in as
 * a <link> so a stylesheet's relative @import still resolves.
 */
export class TemplateLoader {
  constructor(fetchFn = globalThis.fetch?.bind(globalThis)) {
    this._fetch = fetchFn;
    this._html = new Map();
  }

  html(url) {
    if (!url) return Promise.resolve("");
    if (!this._html.has(url)) {
      this._html.set(
        url,
        this._fetch(url).then((res) => {
          if (!res.ok) throw new Error(`template ${url}: HTTP ${res.status}`);
          return res.text();
        }),
      );
    }
    return this._html.get(url);
  }

  styleNode(doc, url) {
    const link = doc.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    return link;
  }
}

export const templateLoader = new TemplateLoader();
