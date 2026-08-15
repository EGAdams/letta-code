/**
 * MermaidView — one reusable Mermaid renderer with mermaid.live-style viewing.
 *
 * Every diagram in the workspace goes through this class, so the pan/zoom
 * wiring exists once instead of being copy-pasted into each tab.
 *
 * Two known hazards on dashboard Project Plans pages, both handled here:
 *
 * 1. **Hidden-tab false "Syntax error in text".** These pages load inside an
 *    iframe in a `.view{display:none}` section. Mermaid measures text with
 *    `getBBox()`, which returns 0 while hidden, and then renders an error
 *    placeholder for perfectly valid source. `whenVisible()` defers the first
 *    render until the document actually has layout.
 * 2. **`svg-pan-zoom` needs a bounded box** to `fit`/`center` against, so each
 *    diagram lives in a fixed-height `.mermaid-wrap` with `overflow:hidden`.
 *
 * `mermaid` and `svgPanZoom` are injected rather than read off `window`, so the
 * class is unit-testable without the CDN bundles.
 */

const DEFAULT_MERMAID_CONFIG = {
  startOnLoad: false,
  theme: "neutral",
  securityLevel: "loose",
  // Without wrap, a long `Note over X` on a narrow participant renders wider
  // than the canvas and is silently clipped by the wrapper's overflow:hidden.
  sequence: { wrap: true },
  flowchart: { htmlLabels: true, curve: "basis" },
};

let seq = 0;
const nextId = () => {
  seq += 1;
  return `mmd-${Date.now().toString(36)}-${seq}`;
};

export class MermaidView {
  constructor({
    mermaid,
    svgPanZoom = null,
    doc = globalThis.document,
    win = globalThis,
    config = {},
  } = {}) {
    if (!mermaid) throw new Error("MermaidView requires the mermaid library");
    this._mermaid = mermaid;
    this._svgPanZoom = svgPanZoom;
    this._doc = doc;
    this._win = win;
    this._instances = [];
    this._visible = null;
    this._renderQueue = Promise.resolve();
    this._mermaid.initialize({ ...DEFAULT_MERMAID_CONFIG, ...config });
  }

  /**
   * Resolve once the document has real layout. Diagrams rendered before this
   * measure as zero-width and come out as "Syntax error in text".
   *
   * Memoized, and awaited inside `render()` rather than by the caller: a
   * top-level `await` in the page's boot module would block module evaluation
   * while the tab is hidden, which in turn holds the iframe's `load` event open
   * for as long as the user never opens the tab.
   */
  whenVisible({ intervalMs = 150 } = {}) {
    if (this._visible) return this._visible;
    this._visible = new Promise((resolve) => {
      const check = () => {
        if ((this._doc.body?.offsetWidth || 0) > 0) {
          resolve();
          return;
        }
        this._win.setTimeout(check, intervalMs);
      };
      check();
    });
    return this._visible;
  }

  /**
   * Mermaid keeps parser/render state in its singleton. Hash changes can ask
   * two tabs to render at once, so serialize calls instead of letting that
   * shared state report a bogus parse failure for otherwise valid source.
   */
  _renderDiagram(code) {
    const job = this._renderQueue.then(() =>
      this._mermaid.render(nextId(), code),
    );
    // A failed diagram must not poison the queue for every diagram after it.
    this._renderQueue = job.then(
      () => undefined,
      () => undefined,
    );
    return job;
  }

  _el(tag, className, props = {}) {
    const el = this._doc.createElement(tag);
    if (className) el.className = className;
    Object.assign(el, props);
    return el;
  }

  /**
   * Render one diagram into `parent` and return its wrapper element.
   * @param {Element} parent
   * @param {{title?: string, caption?: string, code: string}} diagram
   */
  async render(parent, { title = "", caption = "", code }) {
    const figure = this._el("figure", "diagram");
    if (title)
      figure.append(
        this._el("figcaption", "diagram-title", { textContent: title }),
      );

    const wrap = this._el("div", "mermaid-wrap");
    const host = this._el("div", "mermaid");
    wrap.append(host);
    wrap.append(
      this._el("div", "mermaid-hint", {
        textContent: "scroll = zoom · drag = pan",
      }),
    );
    wrap.append(this._buildControls(wrap));
    figure.append(wrap);
    if (caption)
      figure.append(this._el("p", "diagram-caption", { textContent: caption }));
    parent.append(figure);

    try {
      await this.whenVisible();
      const { svg } = await this._renderDiagram(code);
      host.innerHTML = svg;
    } catch (error) {
      // A broken diagram must not take the rest of the tab down with it.
      wrap.classList.add("mermaid-failed");
      host.innerHTML = "";
      host.append(
        this._el("pre", "mermaid-error", {
          textContent: `Diagram failed to render: ${error?.message || error}\n\n${code}`,
        }),
      );
      return figure;
    }
    this._attachPanZoom(wrap);
    return figure;
  }

  _buildControls(wrap) {
    const bar = this._el("div", "mermaid-controls");
    const button = (label, title, action) => {
      const b = this._el("button", "mermaid-btn", {
        type: "button",
        textContent: label,
        title,
      });
      b.addEventListener("click", () => {
        const pz = wrap.__panzoom;
        if (pz) action(pz);
      });
      return b;
    };
    bar.append(
      button("−", "Zoom out", (pz) => pz.zoomOut()),
      button("+", "Zoom in", (pz) => pz.zoomIn()),
      button("Fit", "Fit to frame", (pz) => {
        pz.resize();
        pz.fit();
        pz.center();
      }),
      button("Reset", "Reset zoom and position", (pz) => {
        pz.reset();
        pz.center();
      }),
    );
    return bar;
  }

  _attachPanZoom(wrap) {
    const svg = wrap.querySelector("svg");
    if (!svg || !this._svgPanZoom) return;
    // Mermaid emits a fixed height plus max-width; both fight the pan/zoom
    // viewport, which wants to own the SVG's box.
    svg.removeAttribute("height");
    svg.style.maxWidth = "none";
    svg.style.width = "100%";
    svg.style.height = "100%";
    const pz = this._svgPanZoom(svg, {
      zoomEnabled: true,
      panEnabled: true,
      controlIconsEnabled: false,
      mouseWheelZoomEnabled: true,
      // Scopes wheel capture to the SVG, so the page still scrolls normally
      // when the pointer is outside a diagram.
      preventMouseEventsDefault: true,
      fit: true,
      center: true,
      minZoom: 0.3,
      maxZoom: 14,
      zoomScaleSensitivity: 0.35,
    });
    wrap.__panzoom = pz;
    const onResize = () => {
      pz.resize();
      pz.fit();
      pz.center();
    };
    // svg-pan-zoom measures at construction, which happens in the same tick the
    // figure was appended — before the browser has laid the SVG out at its real
    // size. Without this second pass the diagram fits but sits off-centre.
    (this._win.requestAnimationFrame || ((fn) => this._win.setTimeout(fn, 0)))(
      onResize,
    );
    this._win.addEventListener("resize", onResize);
    this._instances.push({ pz, onResize });
  }

  /** Tear down every diagram this view created (called when a tab is replaced). */
  destroyAll() {
    for (const { pz, onResize } of this._instances) {
      this._win.removeEventListener("resize", onResize);
      try {
        pz.destroy();
      } catch {
        /* already gone with its DOM node */
      }
    }
    this._instances = [];
  }
}
