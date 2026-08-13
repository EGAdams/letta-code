---
name: mermaid-pan-zoom-dashboard-plans
description: Add mouse-wheel zoom and drag-to-pan (like mermaid.live) to Mermaid diagrams on a dashboard Project Plans page (notes_plans_handoffs/*.html), avoid the "Syntax error in text" false-positive these pages get because their tab starts display:none, and default to sequenceDiagram for diagram type unless told otherwise. Use when adding or fixing Mermaid diagrams anywhere under dashboard/dashboard.html's Project Plans nav.
---

# Mermaid pan/zoom + hidden-tab render fix (dashboard Project Plans pages)

## Default diagram type: sequenceDiagram

**Default to `sequenceDiagram` for every diagram on these pages unless EG says otherwise.**
Standing preference (2026-08-11) — don't reach for `flowchart`/`xychart-beta`/etc. by default even
when the content looks more naturally like a node graph or a time series; recast it as a sequence
of participants and messages instead. Only diverge from this if the user explicitly asks for a
different diagram type. `notes_plans_handoffs/swarmforge_project.html` was fully converted to this
convention — see it for worked examples of recasting a topology diagram (participants + handoff
messages), a before/after comparison (two participants exchanging checks), a causal chain
(participants passing a failure down a chain), and a time series (a `loop` of repeated checks vs.
one real check) all as sequence diagrams. Useful non-obvious sequenceDiagram constructs for this:
`rect rgb(r,g,b) ... end` to highlight/color specific messages (used for marking bug locations),
`A--xB: text` for a "message that should have been sent but wasn't", and `loop ... end` for a
repeated polling pattern.

Two rendering problems that always show up together on these pages, and one fix that covers both.

## Problem 1: false "Syntax error in text" on valid diagrams

Project Plans tabs are `<section class="view">` with `.view{display:none}` in
`dashboard/css/dashboard.css` — hidden until clicked. The iframe's `src` loads eagerly regardless,
so `mermaid.initialize({startOnLoad:true})` fires while still hidden. `sequenceDiagram` layout
needs real SVG text measurements (`getBBox()`), which return 0 while hidden — Mermaid then shows
a "Syntax error in text" placeholder even though the diagram source is 100% valid. Flowcharts
tolerate this; sequence diagrams don't. Confirmed root cause: the exact same file renders fine
navigated to directly, and breaks only when embedded in the dashboard's hidden tab.

**Fix — defer until the page actually has layout, don't use `startOnLoad:true`. Also pass
`sequence:{wrap:true}`** — without it, a `Note over X: <long text>` anchored on a narrow
participant span (or a participant near the diagram's right edge, with nothing further right to
give it room) can render wider than the diagram's own canvas and get silently clipped by the
`.mermaid-wrap` container's `overflow:hidden`, even though the diagram parses and "renders"
without error. Widen the note's span (e.g. `Note over Coder,Daemon:` instead of `Note over
Daemon:`) if wrapping alone still isn't enough room:
```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
<script>
  mermaid.initialize({startOnLoad:false, theme:'neutral', securityLevel:'loose', sequence:{wrap:true}});
  (function renderWhenVisible(){
    if (document.body.offsetWidth > 0) {
      mermaid.run().then(attachPanZoom);
    } else {
      setTimeout(renderWhenVisible, 150);
    }
  })();
</script>
```

## Problem 2: adding mouse-wheel zoom / drag-to-pan (like mermaid.live)

Wrap each `<div class="mermaid">…</div>` in a **fixed-height, `overflow:hidden`** container —
`svg-pan-zoom`'s `fit`/`center` need a bounded box to size against:

```css
.mermaid-wrap{position:relative;border:1px solid var(--rule);border-radius:8px;
  margin:16px 0;height:440px;overflow:hidden}
.mermaid-wrap .mermaid{padding:16px;text-align:center;height:100%}
.mermaid-wrap svg{width:100%;height:100%;cursor:grab}
```
```html
<div class="mermaid-wrap">
  <div class="mermaid">
    flowchart LR
      A --> B
  </div>
</div>
```

Then wire pan-zoom in the same script as the render fix above:
```js
function attachPanZoom(){
  document.querySelectorAll('.mermaid-wrap').forEach(wrap => {
    const svg = wrap.querySelector('svg');
    if (!svg) return;
    svg.removeAttribute('height');
    svg.style.maxWidth = 'none';
    const pz = svgPanZoom(svg, {
      zoomEnabled: true, panEnabled: true, mouseWheelZoomEnabled: true,
      preventMouseEventsDefault: true,   // scopes wheel-capture to the SVG only —
                                          // page scroll outside diagrams still works
      fit: true, center: true, minZoom: 0.4, maxZoom: 12, zoomScaleSensitivity: 0.35
    });
    wrap.__panzoom = pz;
    window.addEventListener('resize', () => { pz.resize(); pz.fit(); pz.center(); });
  });
}
```

Optional per-diagram reset button: `<button onclick="wrap.__panzoom.reset()">Reset</button>`
(reference the specific `.mermaid-wrap` element, not a shared global).

## Verifying it actually worked

Don't trust a screenshot alone. Use Playwright and:
1. Navigate the real dashboard (`http://localhost:8765/`), click the Project Plans tab, then the
   specific sub-tab — not the raw iframe URL directly, which won't reproduce the hidden-tab bug.
2. Check every `.mermaid-wrap` has a real `<svg>` child and no `"Syntax error"` text in
   `iframe.contentDocument`.
3. For zoom: use `page.mouse.move()` + `page.mouse.wheel()` (a real trusted wheel event) and read
   `wrap.__panzoom.getZoom()` before/after. **`dispatchEvent(new WheelEvent(...))` does NOT
   reliably trigger `svg-pan-zoom`** — it needs a trusted event, not a synthetic one.
4. Confirm page scroll still works when the wheel event happens *outside* a `.mermaid-wrap`.

Full worked example with 10 `sequenceDiagram`s (originally a mix of flowcharts/xychart, converted
per the default-to-sequence rule above), all fixed and pan-zoomable:
`notes_plans_handoffs/swarmforge_project.html`.
