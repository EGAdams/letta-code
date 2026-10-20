var __defProp = Object.defineProperty;
var __returnValue = (v) => v;
function __exportSetter(name, newValue) {
  this[name] = __returnValue.bind(null, newValue);
}
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, {
      get: all[name],
      enumerable: true,
      configurable: true,
      set: __exportSetter.bind(all, name)
    });
};
var __legacyDecorateClassTS = function(decorators, target, key, desc) {
  var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
  if (typeof Reflect === "object" && typeof Reflect.decorate === "function")
    r = Reflect.decorate(decorators, target, key, desc);
  else
    for (var i = decorators.length - 1;i >= 0; i--)
      if (d = decorators[i])
        r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
  return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __esm = (fn, res) => () => (fn && (res = fn(fn = 0)), res);

// ../../../the-factory/src/utils.ts
function wrap(importComponent, className, observedAttributes) {
  class CustomComponent extends HTMLElement {
    _newComponentInstance = {};
    _connected = false;
    _loaded = false;
    _componentConstructor = {};
    _changedAttributes = false;
    _attrArr = [];
    static originalObservedAttributes;
    static get observedAttributes() {
      return observedAttributes;
    }
    constructor() {
      super();
      const shadow = this.attachShadow({ mode: "open" });
      importComponent().then((component) => {
        this._componentConstructor = component[className];
        this._newComponentInstance = new this._componentConstructor(shadow, shadow.host);
        this._componentConstructor.prototype?.properties?.forEach((componentPrototypeProperty) => {
          Object.defineProperty(this, componentPrototypeProperty, {
            get: () => {
              return this._newComponentInstance[componentPrototypeProperty];
            },
            set: (val) => {
              this._newComponentInstance[componentPrototypeProperty] = val;
            }
          });
        });
        shadow.innerHTML = this._newComponentInstance.sourceHtmlText;
        const firstChild = shadow.firstChild;
        const styleTag = document.createElement("style");
        styleTag.innerHTML = this._newComponentInstance?.sourceStyleText;
        shadow.insertBefore(styleTag, firstChild);
        this._loaded = true;
        if (this._connected) {
          this._connectComponent();
        }
        this.dispatchEvent(new Event("ready"));
      });
    }
    _connectComponent() {
      this._newComponentInstance.connectedCallback();
      if (!this._changedAttributes) {
        this._attrArr.forEach((attr) => this._newComponentInstance.attributeChangedCallback(attr.name, attr.oldValue, attr.newValue));
        this._attrArr = [];
        this._changedAttributes = true;
      }
    }
    connectedCallback() {
      this._connected = true;
      if (this._loaded) {
        this._connectComponent();
      }
    }
    disconnectedCallback() {
      this._connected = false;
      if (this._loaded) {
        this._newComponentInstance.disconnectedCallback();
      }
    }
    adoptedCallback() {
      if (this._loaded) {
        this._newComponentInstance.adoptedCallback();
      }
    }
    attributeChangedCallback(name, oldValue, newValue) {
      if (!this._changedAttributes) {
        this._attrArr.push({ name, oldValue, newValue });
      } else {
        this._newComponentInstance?.attributeChangedCallback(name, oldValue, newValue);
      }
    }
  }
  return CustomComponent;
}
function Component(meta) {
  return (target) => {
    target.prototype.sourceHtmlText = meta?.html || "";
    target.prototype.sourceStyleText = meta?.style || "";
    target.prototype.properties = meta?.properties || [];
  };
}

// ../../../the-factory/src/components/manual-toc/manual-toc.html
var manual_toc_default = `<nav aria-label="Table of contents"><h2>Contents</h2><slot></slot><p class="empty" role="status" hidden>No chapters match your search.</p></nav>
`;
var init_manual_toc = () => {};

// ../../../the-factory/src/components/manual-toc/styles/main.css
var main_default = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; } h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .12em; color: var(--manual-muted); } ::slotted(a) { display: block; padding: .8rem .9rem; margin: .2rem 0; border-radius: .5rem; color: var(--manual-ink); text-decoration: none; font-size: .95rem; line-height: 1.4; } ::slotted(a[aria-current]) { background: #e0eee8; color: #155b48; font-weight: 700; } ::slotted(a[hidden]) { display: none; } ::slotted(a:focus-visible) { outline: 3px solid #167e65; outline-offset: 2px; } .empty { color: var(--manual-muted); }
`;
var init_main = () => {};

// ../../../the-factory/src/components/training-manual/interfaces/component.ts
class ManualComponent {
  $el;
  $host;
  constructor($el, $host) {
    this.$el = $el;
    this.$host = $host;
  }
  connectedCallback() {
    this.render();
  }
  disconnectedCallback() {}
  adoptedCallback() {}
  attributeChangedCallback(_name, _oldValue, _newValue) {
    this.render();
  }
  attribute(name) {
    return this.$host.getAttribute(name) || "";
  }
  emit(name, detail) {
    this.$host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
  }
}

// ../../../the-factory/src/components/manual-toc/manual-toc.component.ts
var exports_manual_toc_component = {};
__export(exports_manual_toc_component, {
  ManualToc: () => ManualToc
});
var ManualToc;
var init_manual_toc_component = __esm(() => {
  init_manual_toc();
  init_main();
  ManualToc = class ManualToc extends ManualComponent {
    constructor($el, $host) {
      super($el, $host);
      $host.addEventListener("click", (event) => {
        const click = event;
        const link = click.target.closest("a[data-chapter]");
        if (!link || click.ctrlKey || click.metaKey || click.shiftKey || click.altKey)
          return;
        click.preventDefault();
        this.emit("manual-navigate", { id: link.dataset.chapter });
      });
    }
    render() {
      for (const link of this.$host.querySelectorAll("a[data-chapter]")) {
        if (link.getAttribute("data-chapter") === this.attribute("current"))
          link.setAttribute("aria-current", "page");
        else
          link.removeAttribute("aria-current");
      }
      this.$el.querySelector(".empty").hidden = this.attribute("matches") !== "0";
    }
  };
  ManualToc = __legacyDecorateClassTS([
    Component({ html: manual_toc_default, style: main_default, properties: [] })
  ], ManualToc);
});

// ../../../the-factory/src/components/manual-chapter/manual-chapter.html
var manual_chapter_default = `<article aria-labelledby="chapter-title"><header><p class="eyebrow">TRAINING GUIDE</p><h2 id="chapter-title" tabindex="-1"></h2><p class="summary"></p></header><slot></slot></article>
`;
var init_manual_chapter = () => {};

// ../../../the-factory/src/components/manual-chapter/styles/main.css
var main_default2 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; } :host([hidden]) { display: none; } article { max-width: 860px; margin: auto; } h2 { font: 650 clamp(1.7rem, 3vw, 2.4rem)/1.15 system-ui; margin: .5rem 0 1rem; letter-spacing: -.03em; } .eyebrow { color: var(--manual-accent); letter-spacing: .14em; font: 700 .72rem system-ui; } .summary { color: var(--manual-muted); font-size: 1.1rem; line-height: 1.65; margin-bottom: 2rem; } ::slotted(p) { line-height: 1.8; } ::slotted(a) { display: block; margin: 1rem 0; color: var(--manual-accent); } ::slotted(*) { margin-bottom: 1.2rem; }
`;
var init_main2 = () => {};

// ../../../the-factory/src/components/manual-chapter/manual-chapter.component.ts
var exports_manual_chapter_component = {};
__export(exports_manual_chapter_component, {
  ManualChapter: () => ManualChapter
});
var ManualChapter;
var init_manual_chapter_component = __esm(() => {
  init_manual_chapter();
  init_main2();
  ManualChapter = class ManualChapter extends ManualComponent {
    render() {
      this.$el.querySelector("h2").textContent = this.attribute("heading");
      this.$el.querySelector(".summary").textContent = this.attribute("summary");
    }
  };
  ManualChapter = __legacyDecorateClassTS([
    Component({ html: manual_chapter_default, style: main_default2, properties: [] })
  ], ManualChapter);
});

// ../../../the-factory/src/components/manual-progress/manual-progress.html
var manual_progress_default = `<section aria-label="Practice progress"><p><strong>Practice checklist</strong><span class="count"></span></p><progress aria-label="Practice steps checked" value="0" max="1"></progress><small>Your checkmarks record practice, not verified expense saves.</small></section>
`;
var init_manual_progress = () => {};

// ../../../the-factory/src/components/manual-progress/styles/main.css
var main_default3 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; margin: 1.5rem 0; } section { border-top: 1px solid var(--manual-line); padding-top: 1rem; } p { display: flex; justify-content: space-between; font-size: .8rem; gap: 1rem; } progress { width: 100%; height: .55rem; accent-color: var(--manual-accent); } small { display: block; margin-top: .6rem; color: var(--manual-muted); line-height: 1.5; }
`;
var init_main3 = () => {};

// ../../../the-factory/src/components/manual-progress/manual-progress.component.ts
var exports_manual_progress_component = {};
__export(exports_manual_progress_component, {
  ManualProgress: () => ManualProgress
});
var ManualProgress;
var init_manual_progress_component = __esm(() => {
  init_manual_progress();
  init_main3();
  ManualProgress = class ManualProgress extends ManualComponent {
    render() {
      const total = Math.max(1, Number(this.attribute("total")) || 1);
      const done = Math.max(0, Math.min(total, Number(this.attribute("done")) || 0));
      const progress = this.$el.querySelector("progress");
      progress.max = total;
      progress.value = done;
      this.$el.querySelector(".count").textContent = `${done} / ${total}`;
    }
  };
  ManualProgress = __legacyDecorateClassTS([
    Component({ html: manual_progress_default, style: main_default3, properties: [] })
  ], ManualProgress);
});

// ../../../the-factory/src/components/training-step/training-step.html
var training_step_default = `<section><h3></h3><p></p><slot></slot><label><input type="checkbox"> I tried this step</label></section>
`;
var init_training_step = () => {};

// ../../../the-factory/src/components/training-step/styles/main.css
var main_default4 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; } section { padding: 1.3rem; border: 1px solid var(--manual-line); border-radius: .8rem; background: white; } h3 { margin: 0; font-size: 1.1rem; } p { line-height: 1.7; } label { display: flex; align-items: center; gap: .6rem; font-size: .85rem; color: var(--manual-muted); margin-top: 1rem; cursor: pointer; } input { width: 1.1rem; height: 1.1rem; accent-color: var(--manual-accent); }
`;
var init_main4 = () => {};

// ../../../the-factory/src/components/training-step/training-step.component.ts
var exports_training_step_component = {};
__export(exports_training_step_component, {
  TrainingStep: () => TrainingStep
});
var TrainingStep;
var init_training_step_component = __esm(() => {
  init_training_step();
  init_main4();
  TrainingStep = class TrainingStep extends ManualComponent {
    constructor($el, $host) {
      super($el, $host);
      $el.addEventListener("change", (event) => {
        const input = event.target;
        if (input.type === "checkbox")
          this.emit("manual-complete", { id: this.attribute("step-id"), checked: input.checked });
      });
    }
    render() {
      this.$el.querySelector("h3").textContent = this.attribute("heading");
      this.$el.querySelector("p").textContent = this.attribute("text");
      const input = this.$el.querySelector("input");
      input.checked = this.attribute("completed") === "true";
      input.setAttribute("aria-label", `I tried: ${this.attribute("heading")}`);
    }
  };
  TrainingStep = __legacyDecorateClassTS([
    Component({ html: training_step_default, style: main_default4, properties: [] })
  ], TrainingStep);
});

// ../../../the-factory/src/components/training-callout/training-callout.html
var training_callout_default = `<aside><h3></h3><p></p><slot></slot></aside>
`;
var init_training_callout = () => {};

// ../../../the-factory/src/components/training-callout/styles/main.css
var main_default5 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; } aside { padding: 1rem 1.3rem; background: #edf5f1; border-left: 3px solid var(--manual-accent); border-radius: 0 .6rem .6rem 0; } h3 { font-size: 1rem; margin: 0 0 .5rem; } p { margin: 0; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; } :host([tone="planned"]) aside { background: #f5f2e8; border-color: #b58a28; }
`;
var init_main5 = () => {};

// ../../../the-factory/src/components/training-callout/training-callout.component.ts
var exports_training_callout_component = {};
__export(exports_training_callout_component, {
  TrainingCallout: () => TrainingCallout
});
var TrainingCallout;
var init_training_callout_component = __esm(() => {
  init_training_callout();
  init_main5();
  TrainingCallout = class TrainingCallout extends ManualComponent {
    render() {
      this.$el.querySelector("h3").textContent = this.attribute("heading") || "Remember";
      this.$el.querySelector("p").textContent = this.attribute("text");
    }
  };
  TrainingCallout = __legacyDecorateClassTS([
    Component({ html: training_callout_default, style: main_default5, properties: [] })
  ], TrainingCallout);
});

// ../../../the-factory/src/components/command-example/command-example.html
var command_example_default = `<div class="example"><pre><code></code></pre><button type="button">Copy example</button></div><p role="status"></p>
`;
var init_command_example = () => {};

// ../../../the-factory/src/components/command-example/styles/main.css
var main_default6 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; }

* { box-sizing: border-box; } button { font: inherit; color: inherit; border: 1px solid #a4bbb0; border-radius: .4rem; background: white; padding: .5rem .7rem; cursor: pointer; } button:hover { background: #e9f2ed; } button:focus-visible, input:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; } :host([hidden]) { display: none; }

:host { display: block; } .example { background: #f2f4f3; border: 1px solid var(--manual-line); border-radius: .5rem; padding: .8rem; display: flex; align-items: flex-start; gap: .8rem; } pre { flex: 1; min-width: 0; white-space: pre-wrap; overflow-wrap: anywhere; margin: .35rem 0; font: .9rem/1.65 ui-monospace, monospace; } button { flex: none; } p { font-size: .85rem; color: var(--manual-muted); margin: .5rem 0 0; } @media (max-width: 520px) { .example { flex-direction: column; } }
`;
var init_main6 = () => {};

// ../../../the-factory/src/components/command-example/command-example.component.ts
var exports_command_example_component = {};
__export(exports_command_example_component, {
  CommandExample: () => CommandExample
});
var CommandExample;
var init_command_example_component = __esm(() => {
  init_command_example();
  init_main6();
  CommandExample = class CommandExample extends ManualComponent {
    constructor($el, $host) {
      super($el, $host);
      $el.addEventListener("click", (event) => {
        if (!event.target.closest("button"))
          return;
        this.emit("manual-copy", {
          text: this.attribute("example"),
          respond: (message) => {
            this.$el.querySelector('[role="status"]').textContent = message;
          }
        });
      });
    }
    render() {
      this.$el.querySelector("code").textContent = this.attribute("example");
    }
  };
  CommandExample = __legacyDecorateClassTS([
    Component({ html: command_example_default, style: main_default6, properties: [] })
  ], CommandExample);
});

// ../../../the-factory/src/components/training-manual/training-manual.html
var training_manual_default = `<header class="masthead">
	<div><p class="eyebrow">ROL FINANCE · LEARNING LAB</p><h1>Training manual</h1><p>Learn the workflow. See the evidence. Keep your place.</p></div>
	<a href="/" target="_blank" rel="noopener">Open Toyota in another tab ↗</a>
</header>
<div class="layout">
	<aside class="sidebar">
		<button class="skip" data-action="content" type="button">Skip to chapter</button>
		<label for="manual-search">Search this manual</label>
		<input id="manual-search" type="search" placeholder="Try “receipt” or “interface”…" autocomplete="off">
		<manual-toc></manual-toc>
		<manual-progress></manual-progress>
		<button type="button" data-action="reset">Reset practice checkmarks</button>
		<p class="storage" role="status"></p>
	</aside>
	<main>
		<div class="chapters"></div>
		<nav class="pager" aria-label="Chapter navigation">
			<button type="button" data-action="previous">Previous chapter</button>
			<span class="position" aria-live="polite"></span>
			<button type="button" data-action="next">Next chapter</button>
		</nav>
	</main>
</div>
`;
var init_training_manual = () => {};

// ../../../the-factory/src/components/training-manual/styles/main.css
var main_default7 = `:host { --manual-accent: #176b54; --manual-ink: #20362e; --manual-muted: #54685f; --manual-line: #d6e1da; color: var(--manual-ink); font-family: system-ui, sans-serif; display: block; }

* { box-sizing: border-box; }
button, input { font: inherit; }
button, a, input { -webkit-tap-highlight-color: transparent; }
button { border: 1px solid #a4bbb0; border-radius: .4rem; padding: .65rem .8rem; background: white; color: var(--manual-ink); cursor: pointer; }
button:hover:not(:disabled) { background: #e9f2ed; }
button:disabled { opacity: .45; cursor: default; }
:focus-visible { outline: 3px solid #167e65; outline-offset: 3px; }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }

.masthead { display: flex; justify-content: space-between; align-items: center; gap: 2rem; padding: 2rem 3rem; border-bottom: 1px solid var(--manual-line); background: #f3f7f3; }
.eyebrow { letter-spacing: .13em; font-size: .7rem; font-weight: 750; color: var(--manual-accent); }
h1 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin: .4rem 0; letter-spacing: -.04em; }
.masthead p:last-child { color: var(--manual-muted); margin-bottom: 0; }
.masthead a { color: var(--manual-accent); font-size: .85rem; white-space: nowrap; }
.layout { display: grid; grid-template-columns: 290px minmax(0, 1fr); max-width: 1500px; margin: auto; }
.sidebar { padding: 1.6rem; border-right: 1px solid var(--manual-line); background: #fafbf8; align-self: start; position: sticky; top: 0; max-height: 100vh; overflow-y: auto; }
label { display: block; font-size: .8rem; font-weight: 650; margin: .5rem 0; }
input { width: 100%; border: 1px solid #a4bbb0; border-radius: .4rem; padding: .7rem; background: white; color: var(--manual-ink); }
.skip { margin-bottom: .6rem; font-size: .8rem; }
.storage { font-size: .75rem; line-height: 1.5; color: var(--manual-muted); }
main { padding: 2.6rem clamp(1rem, 4vw, 4rem); min-width: 0; }
.pager { max-width: 860px; margin: 3rem auto 0; padding-top: 1.5rem; border-top: 1px solid var(--manual-line); display: flex; justify-content: space-between; align-items: center; gap: .7rem; }
.position { font-size: .8rem; color: var(--manual-muted); }
@media (max-width: 760px) { .masthead { padding: 1.4rem; display: block; } .masthead a { display: inline-block; margin-top: 1rem; } .layout { display: block; } .sidebar { position: static; max-height: none; border-right: 0; border-bottom: 1px solid var(--manual-line); } main { padding: 1.5rem 1.1rem; } .pager { flex-wrap: wrap; } .position { order: 3; flex-basis: 100%; text-align: center; } }
@media print { .masthead a, .sidebar, .pager { display: none; } .layout { display: block; } main { padding: 0; } }
`;
var init_main7 = () => {};

// ../../../the-factory/src/components/training-manual/training-manual.component.ts
var exports_training_manual_component = {};
__export(exports_training_manual_component, {
  TrainingManual: () => TrainingManual
});
var TrainingManual;
var init_training_manual_component = __esm(() => {
  init_training_manual();
  init_main7();
  TrainingManual = class TrainingManual extends ManualComponent {
    dependencies;
    unsubscribe;
    constructor($el, $host) {
      super($el, $host);
      $el.addEventListener("input", () => this.filter());
      $el.addEventListener("click", (event) => {
        const action = event.target.closest("[data-action]")?.dataset.action;
        const deps = this.dependencies;
        if (!deps || !action)
          return;
        if (action === "reset") {
          deps.session.reset();
          this.render();
          return;
        }
        if (action === "content") {
          this.focusChapter();
          return;
        }
        deps.session.move(action === "next" ? 1 : -1);
        this.navigate();
      });
      $host.addEventListener("manual-navigate", (event) => {
        this.dependencies?.session.select(event.detail.id);
        this.navigate();
      });
      $host.addEventListener("manual-complete", (event) => {
        const detail = event.detail;
        this.dependencies?.session.complete(detail.id, detail.checked);
        this.render();
      });
      $host.addEventListener("manual-copy", (event) => {
        const detail = event.detail;
        this.dependencies?.clipboard.copy(detail.text).then(() => detail.respond("Copied. Paste this into Toyota’s conversation when you are ready."), () => detail.respond("Copy unavailable. Select the example text and copy it manually."));
      });
    }
    initialize = (dependencies) => {
      this.unsubscribe?.();
      this.unsubscribe = undefined;
      this.dependencies = dependencies;
      const doc = this.$host.ownerDocument;
      const toc = this.$el.querySelector("manual-toc");
      const chapters = this.$el.querySelector(".chapters");
      toc.replaceChildren();
      chapters.replaceChildren();
      this.$el.querySelector("h1").textContent = dependencies.manual.title;
      for (const [index, chapter] of dependencies.manual.chapters.entries()) {
        const link = doc.createElement("a");
        link.href = `#${chapter.id}`;
        link.dataset.chapter = chapter.id;
        link.textContent = `${String(index + 1).padStart(2, "0")}  ${chapter.title}`;
        toc.append(link);
        const section = doc.createElement("manual-chapter");
        section.dataset.chapter = chapter.id;
        section.setAttribute("heading", chapter.title);
        section.setAttribute("summary", chapter.summary);
        for (const block of chapter.blocks)
          section.append(dependencies.blocks.create(block));
        chapters.append(section);
      }
      this.observe();
      this.render();
    };
    connectedCallback() {
      this.observe();
      this.render();
    }
    disconnectedCallback() {
      this.unsubscribe?.();
      this.unsubscribe = undefined;
    }
    render() {
      const deps = this.dependencies;
      if (!deps)
        return;
      const { session, manual } = deps;
      for (const chapter of this.$el.querySelectorAll("manual-chapter")) {
        chapter.hidden = chapter.dataset.chapter !== session.chapter.id;
      }
      for (const step of this.$el.querySelectorAll("training-step")) {
        step.setAttribute("completed", String(session.completed.includes(step.getAttribute("step-id"))));
      }
      const index = manual.chapters.findIndex((chapter) => chapter.id === session.chapter.id);
      this.$el.querySelector('[data-action="previous"]').disabled = index === 0;
      this.$el.querySelector('[data-action="next"]').disabled = index === manual.chapters.length - 1;
      this.$el.querySelector(".position").textContent = `Chapter ${index + 1} of ${manual.chapters.length}`;
      this.$el.querySelector("manual-toc").setAttribute("current", session.chapter.id);
      const progress = this.$el.querySelector("manual-progress");
      progress.setAttribute("done", String(session.completed.length));
      progress.setAttribute("total", String(session.stepCount));
      this.$el.querySelector(".storage").textContent = session.persistenceAvailable ? "Reading position and checkmarks stay in this browser." : "Browser storage is unavailable. Progress lasts until this page closes.";
      this.filter();
    }
    observe() {
      if (!this.dependencies || this.unsubscribe)
        return;
      this.unsubscribe = this.dependencies.navigation.subscribe(() => {
        this.dependencies.session.select(this.dependencies.navigation.current());
        this.render();
        this.focusChapter();
      });
    }
    navigate() {
      if (!this.dependencies)
        return;
      this.dependencies.navigation.visit(this.dependencies.session.chapter.id);
      this.render();
      this.focusChapter();
    }
    filter() {
      if (!this.dependencies)
        return;
      const input = this.$el.querySelector('input[type="search"]');
      const matches = this.dependencies.session.search(input.value).map((chapter) => chapter.id);
      for (const link of this.$el.querySelectorAll("a[data-chapter]")) {
        link.hidden = !matches.includes(link.dataset.chapter);
      }
      this.$el.querySelector("manual-toc").setAttribute("matches", String(matches.length));
    }
    focusChapter() {
      const chapter = this.$el.querySelector("manual-chapter:not([hidden])");
      chapter?.shadowRoot?.querySelector("h2")?.focus({ preventScroll: true });
      chapter?.scrollIntoView({ block: "start" });
    }
  };
  TrainingManual = __legacyDecorateClassTS([
    Component({ html: training_manual_default, style: main_default7, properties: ["initialize"] })
  ], TrainingManual);
});

// ../../../the-factory/src/components/workflow-phase/workflow-phase.html
var workflow_phase_default = `<article>
	<header><h4></h4><span class="status"></span></header>
	<p class="description"></p>
	<p class="times"></p>
</article>
`;
var init_workflow_phase = () => {};

// ../../../the-factory/src/components/workflow-phase/styles/main.css
var main_default8 = `:host { --phase-border: #d6e3dc; }

:host([status="Failed"]) .status { color: #922b24; }
:host([status="Completed"]) .status { color: #1b614b; }

:host { display: block; }
article { padding: 1rem; border: 1px solid var(--phase-border); border-radius: .6rem; background: white; }
header { display: flex; gap: .75rem; align-items: baseline; justify-content: space-between; flex-wrap: wrap; }
h4 { margin: 0; font-size: 1rem; overflow-wrap: anywhere; }
.status { font-weight: 700; font-size: .85rem; }
p { line-height: 1.6; margin: .5rem 0 0; overflow-wrap: anywhere; }
.times { font-size: .8rem; color: #53665c; }
`;
var init_main8 = () => {};

// ../../../the-factory/src/components/workflow-phase/workflow-phase.component.ts
var exports_workflow_phase_component = {};
__export(exports_workflow_phase_component, {
  WorkflowPhase: () => WorkflowPhase
});
var WorkflowPhase;
var init_workflow_phase_component = __esm(() => {
  init_workflow_phase();
  init_main8();
  WorkflowPhase = class WorkflowPhase extends ManualComponent {
    render() {
      this.$el.querySelector("h4").textContent = this.attribute("heading");
      this.$el.querySelector(".description").textContent = this.attribute("description");
      this.$el.querySelector(".status").textContent = this.attribute("status");
      this.$el.querySelector(".times").textContent = `Started: ${this.attribute("started") || "not in this trace"} · Ended: ${this.attribute("ended") || "not recorded"}`;
    }
  };
  WorkflowPhase = __legacyDecorateClassTS([
    Component({ html: workflow_phase_default, style: main_default8, properties: [] })
  ], WorkflowPhase);
});

// ../../../the-factory/src/components/workflow-inspector/workflow-inspector.html
var workflow_inspector_default = `<section aria-label="Workflow evidence">
	<header><h3>Workflow evidence</h3><button type="button">Refresh evidence</button></header>
	<p class="notice">Read-only snapshot. Refresh after Toyota finishes a request. This does not start a workflow or save an expense.</p>
	<p role="status" aria-live="polite"></p>
	<p role="alert" hidden></p>
	<label>ADW run <select aria-label="ADW run"><option value="">Latest run</option></select></label>
	<div class="evidence" hidden>
		<h4>Current saved checkpoint</h4>
		<dl></dl>
		<p class="checkpoint-message"></p>
		<p class="notice">The category above is retained checkpoint data, not a fresh expense database read. A historical run may describe an earlier action or expense.</p>
		<h4 class="run-heading"></h4>
		<p class="recorded-at"></p>
		<p class="trace-note"></p>
		<ol aria-label="Recorded phases"></ol>
		<slot name="run-link"></slot>
		<p class="notice">Completed means the phase finished. Confirm a save through Toyota’s independent stored-value verification. A phase without an ending may be unfinished or absent from this trace.</p>
	</div>
</section>
`;
var init_workflow_inspector = () => {};

// ../../../the-factory/src/components/workflow-inspector/styles/main.css
var main_default9 = `:host { --inspection-border: #c8d9cf; --inspection-accent: #215c48; }

[hidden] { display: none !important; }
button:disabled { opacity: .6; cursor: wait; }
[role="alert"] { color: #922b24; padding: .75rem; background: #fff0e9; }

:host { display: block; min-width: 0; }
section { border: 1px solid var(--inspection-border); border-radius: .8rem; background: #f4f8f5; padding: 1.2rem; }
header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .75rem; }
h3, h4 { margin: .5rem 0; }
p { line-height: 1.7; overflow-wrap: anywhere; }
.notice, .recorded-at { color: #52665a; font-size: .9rem; }
button, select { font: inherit; padding: .65rem .85rem; border: 1px solid var(--inspection-border); border-radius: .4rem; background: white; max-width: 100%; }
button { cursor: pointer; background: var(--inspection-accent); color: white; }
button:focus-visible, select:focus-visible { outline: 3px solid #bd942d; outline-offset: 3px; }
label { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }
dl { display: grid; grid-template-columns: minmax(8rem, 1fr) minmax(0, 2fr); gap: .5rem 1rem; line-height: 1.6; }
dt { font-weight: 600; } dd { margin: 0; overflow-wrap: anywhere; }
ol { padding-left: 1.5rem; } li { margin: .75rem 0; }
@media (max-width: 600px) { dl { grid-template-columns: 1fr; } dd { margin-bottom: .5rem; } section { padding: .85rem; } }
`;
var init_main9 = () => {};

// ../../../the-factory/src/components/workflow-inspector/workflow-inspector.component.ts
var exports_workflow_inspector_component = {};
__export(exports_workflow_inspector_component, {
  WorkflowInspector: () => WorkflowInspector
});
var WorkflowInspector;
var init_workflow_inspector_component = __esm(() => {
  init_workflow_inspector();
  init_main9();
  WorkflowInspector = class WorkflowInspector extends ManualComponent {
    inspector;
    unsubscribe;
    selected = "";
    constructor($el, $host) {
      super($el, $host);
      $el.addEventListener("click", (event) => {
        if (event.target.closest("button"))
          this.inspector?.refresh(this.selected);
      });
      $el.addEventListener("change", (event) => {
        this.selected = event.target.value;
        this.inspector?.refresh(this.selected);
      });
    }
    initialize = (inspector) => {
      this.unsubscribe?.();
      this.inspector?.cancel();
      this.unsubscribe = undefined;
      this.inspector = inspector;
      this.observe();
    };
    connectedCallback() {
      this.observe();
      this.render();
    }
    disconnectedCallback() {
      this.unsubscribe?.();
      this.unsubscribe = undefined;
      this.inspector?.cancel();
    }
    render() {
      this.present(this.inspector?.state || { status: "idle" });
    }
    observe() {
      if (!this.unsubscribe && this.inspector && this.$host.isConnected) {
        this.unsubscribe = this.inspector.subscribe((state) => this.present(state));
      }
    }
    present(state) {
      const doc = this.$host.ownerDocument;
      const loading = state.status === "loading";
      this.$el.querySelector("section").setAttribute("aria-busy", String(loading));
      this.$el.querySelector("button").disabled = loading;
      const select = this.$el.querySelector("select");
      select.disabled = loading;
      this.$el.querySelector('[role="status"]').textContent = loading ? "Reading workflow evidence…" : state.checkedAt ? `Snapshot read at ${new Date(state.checkedAt).toLocaleString()}. Refresh to check for changes.` : "Choose Refresh evidence to read the saved checkpoint and recorded phases.";
      const alert = this.$el.querySelector('[role="alert"]');
      alert.hidden = state.status !== "error";
      alert.textContent = state.error || "";
      this.$el.querySelector(".evidence").hidden = state.status !== "ready";
      this.emit("workflow-run-selected", { id: state.run?.id || "" });
      if (!state.checkpoint)
        return;
      const checkpoint = state.checkpoint;
      select.replaceChildren();
      for (const id of ["", ...[...checkpoint.runs].reverse()]) {
        const option = doc.createElement("option");
        option.value = id;
        option.textContent = id || "Latest run";
        select.append(option);
      }
      select.value = this.selected;
      const list = this.$el.querySelector("dl");
      list.replaceChildren();
      for (const [label, value] of [
        ["Assignment", checkpoint.assignment || "None selected"],
        ["Environment", checkpoint.environment],
        ["Checkpoint status", checkpoint.status],
        ["Selected expense", String(checkpoint.expense ?? "None selected")],
        ["Category at checkpoint", checkpoint.category || "Not recorded"],
        ["Pending browser operation", checkpoint.pending || "None recorded"]
      ]) {
        const term = doc.createElement("dt");
        term.textContent = label;
        const description = doc.createElement("dd");
        description.textContent = value;
        list.append(term, description);
      }
      this.$el.querySelector(".checkpoint-message").textContent = checkpoint.message;
      this.$el.querySelector(".run-heading").textContent = state.run ? `Recorded run ${state.run.id}` : "No ADW runs recorded yet";
      this.$el.querySelector(".recorded-at").textContent = state.run?.recordedAt ? `Last recorded event: ${state.run.recordedAt}` : "";
      this.$el.querySelector(".trace-note").textContent = state.run?.limited ? "This trace contains the latest 500 events. Earlier phases may be missing." : state.run && !state.run.phases.length ? "No phase events are available in this trace." : "";
      const phases = this.$el.querySelector("ol");
      phases.replaceChildren();
      for (const phase of state.run?.phases || []) {
        const item = doc.createElement("li");
        const card = doc.createElement("workflow-phase");
        for (const [key, value] of Object.entries({ heading: phase.name, description: phase.description, status: phase.status, started: phase.started, ended: phase.ended })) {
          card.setAttribute(key, value);
        }
        item.append(card);
        phases.append(item);
      }
    }
  };
  WorkflowInspector = __legacyDecorateClassTS([
    Component({ html: workflow_inspector_default, style: main_default9, properties: ["initialize"] })
  ], WorkflowInspector);
});
// ../../../the-factory/src/components/training-manual/training-manual.observed-attributes.ts
var observedAttributes = [];
var training_manual_observed_attributes_default = observedAttributes;
// ../../../the-factory/src/components/manual-toc/manual-toc.observed-attributes.ts
var observedAttributes2 = ["current", "matches"];
var manual_toc_observed_attributes_default = observedAttributes2;

// ../../../the-factory/src/components/manual-toc/index.ts
var manualTocDefine = () => {
  if (!customElements.get("manual-toc")) {
    customElements.define("manual-toc", wrap(() => Promise.resolve().then(() => (init_manual_toc_component(), exports_manual_toc_component)), "ManualToc", manual_toc_observed_attributes_default));
  }
};
// ../../../the-factory/src/components/manual-chapter/manual-chapter.observed-attributes.ts
var observedAttributes3 = ["heading", "summary"];
var manual_chapter_observed_attributes_default = observedAttributes3;

// ../../../the-factory/src/components/manual-chapter/index.ts
var manualChapterDefine = () => {
  if (!customElements.get("manual-chapter")) {
    customElements.define("manual-chapter", wrap(() => Promise.resolve().then(() => (init_manual_chapter_component(), exports_manual_chapter_component)), "ManualChapter", manual_chapter_observed_attributes_default));
  }
};
// ../../../the-factory/src/components/manual-progress/manual-progress.observed-attributes.ts
var observedAttributes4 = ["done", "total"];
var manual_progress_observed_attributes_default = observedAttributes4;

// ../../../the-factory/src/components/manual-progress/index.ts
var manualProgressDefine = () => {
  if (!customElements.get("manual-progress")) {
    customElements.define("manual-progress", wrap(() => Promise.resolve().then(() => (init_manual_progress_component(), exports_manual_progress_component)), "ManualProgress", manual_progress_observed_attributes_default));
  }
};
// ../../../the-factory/src/components/training-step/training-step.observed-attributes.ts
var observedAttributes5 = ["heading", "text", "step-id", "completed"];
var training_step_observed_attributes_default = observedAttributes5;

// ../../../the-factory/src/components/training-step/index.ts
var trainingStepDefine = () => {
  if (!customElements.get("training-step")) {
    customElements.define("training-step", wrap(() => Promise.resolve().then(() => (init_training_step_component(), exports_training_step_component)), "TrainingStep", training_step_observed_attributes_default));
  }
};
// ../../../the-factory/src/components/training-callout/training-callout.observed-attributes.ts
var observedAttributes6 = ["heading", "text", "tone"];
var training_callout_observed_attributes_default = observedAttributes6;

// ../../../the-factory/src/components/training-callout/index.ts
var trainingCalloutDefine = () => {
  if (!customElements.get("training-callout")) {
    customElements.define("training-callout", wrap(() => Promise.resolve().then(() => (init_training_callout_component(), exports_training_callout_component)), "TrainingCallout", training_callout_observed_attributes_default));
  }
};
// ../../../the-factory/src/components/command-example/command-example.observed-attributes.ts
var observedAttributes7 = ["example"];
var command_example_observed_attributes_default = observedAttributes7;

// ../../../the-factory/src/components/command-example/index.ts
var commandExampleDefine = () => {
  if (!customElements.get("command-example")) {
    customElements.define("command-example", wrap(() => Promise.resolve().then(() => (init_command_example_component(), exports_command_example_component)), "CommandExample", command_example_observed_attributes_default));
  }
};

// ../../../the-factory/src/components/training-manual/index.ts
var trainingManualDefine = () => {
  manualTocDefine();
  manualChapterDefine();
  manualProgressDefine();
  trainingStepDefine();
  trainingCalloutDefine();
  commandExampleDefine();
  if (!customElements.get("training-manual")) {
    customElements.define("training-manual", wrap(() => Promise.resolve().then(() => (init_training_manual_component(), exports_training_manual_component)), "TrainingManual", training_manual_observed_attributes_default));
  }
};

// ../../../the-factory/src/components/training-manual/adapters/browser-ports.ts
class BrowserReadingStore {
  window;
  constructor(window2) {
    this.window = window2;
  }
  read(key) {
    return JSON.parse(this.window.localStorage.getItem(key) || "null");
  }
  write(key, checkpoint) {
    this.window.localStorage.setItem(key, JSON.stringify(checkpoint));
  }
}

class HashChapterNavigation {
  window;
  constructor(window2) {
    this.window = window2;
  }
  current() {
    try {
      return decodeURIComponent(this.window.location.hash.slice(1));
    } catch {
      return "";
    }
  }
  visit(chapter) {
    if (this.current() !== chapter)
      this.window.location.hash = encodeURIComponent(chapter);
  }
  subscribe(changed) {
    this.window.addEventListener("hashchange", changed);
    return () => this.window.removeEventListener("hashchange", changed);
  }
}

class BrowserClipboard {
  navigator;
  constructor(navigator2) {
    this.navigator = navigator2;
  }
  async copy(text) {
    if (!this.navigator.clipboard)
      throw new Error("Clipboard unavailable on this connection.");
    await this.navigator.clipboard.writeText(text);
  }
}

// ../../../the-factory/src/components/training-manual/factory/block-factory.ts
class ManualBlockFactory {
  renderers;
  constructor(renderers) {
    this.renderers = renderers;
  }
  create(block) {
    const renderer = this.renderers.get(block.kind);
    if (!renderer)
      throw new Error(`No renderer registered for "${block.kind}".`);
    return renderer.create(block);
  }
}

class TextRenderer {
  document;
  constructor(document2) {
    this.document = document2;
  }
  create(block) {
    const paragraph = this.document.createElement("p");
    paragraph.textContent = block.text;
    return paragraph;
  }
}

class ComponentRenderer {
  document;
  tag;
  tone;
  constructor(document2, tag, tone = "note") {
    this.document = document2;
    this.tag = tag;
    this.tone = tone;
  }
  create(block) {
    const element = this.document.createElement(this.tag);
    element.setAttribute("heading", block.title || "");
    element.setAttribute("tone", this.tone);
    element.setAttribute("text", block.text);
    if (block.id)
      element.setAttribute("step-id", block.id);
    if (this.tag === "command-example")
      element.setAttribute("example", block.text);
    if (block.prompt) {
      const command = this.document.createElement("command-example");
      command.setAttribute("example", block.prompt);
      element.append(command);
    }
    return element;
  }
}

class LinkRenderer {
  document;
  constructor(document2) {
    this.document = document2;
  }
  create(block) {
    const link = this.document.createElement("a");
    const href = block.href || "";
    if (!/^(https?:\/\/|\/(?!\/)|#)/.test(href))
      throw new Error("Unsupported manual link.");
    link.href = href;
    link.textContent = block.text;
    link.target = "_blank";
    link.rel = "noopener";
    return link;
  }
}
function createDefaultBlockFactory(document2, extensions = new Map) {
  return new ManualBlockFactory(new Map([
    ["text", new TextRenderer(document2)],
    ["step", new ComponentRenderer(document2, "training-step")],
    ["command", new ComponentRenderer(document2, "command-example")],
    ["note", new ComponentRenderer(document2, "training-callout")],
    ["placeholder", new ComponentRenderer(document2, "training-callout", "planned")],
    ["link", new LinkRenderer(document2)],
    ...extensions
  ]));
}

// ../../../the-factory/src/components/training-manual/session/manual-session.ts
class ManualSession {
  manual;
  store;
  position = 0;
  checked = new Set;
  steps;
  key;
  persistenceAvailable = true;
  constructor(manual, store, bookmark) {
    this.manual = manual;
    this.store = store;
    if (!manual.chapters.length)
      throw new Error("A manual needs at least one chapter.");
    this.key = `training-manual:${manual.id}:v${manual.version}`;
    this.steps = new Set(manual.chapters.flatMap((chapter) => chapter.blocks).filter((block) => block.kind === "step" && block.id).map((block) => block.id));
    try {
      const saved = store.read(this.key);
      if (saved && typeof saved === "object") {
        const value = saved;
        if (typeof value.chapter === "string")
          this.position = this.index(value.chapter);
        if (Array.isArray(value.completed)) {
          for (const id of value.completed)
            if (this.steps.has(id))
              this.checked.add(id);
        }
      }
    } catch {
      this.persistenceAvailable = false;
    }
    if (manual.chapters.some((chapter) => chapter.id === bookmark))
      this.position = this.index(bookmark);
    this.save();
  }
  get chapter() {
    return this.manual.chapters[this.position];
  }
  get completed() {
    return [...this.checked];
  }
  get stepCount() {
    return this.steps.size;
  }
  select(id) {
    if (!this.manual.chapters.some((chapter) => chapter.id === id))
      return;
    this.position = this.index(id);
    this.save();
  }
  move(offset) {
    this.position = Math.max(0, Math.min(this.manual.chapters.length - 1, this.position + offset));
    this.save();
  }
  search(query) {
    const needle = query.trim().toLocaleLowerCase();
    return this.manual.chapters.filter((chapter) => [
      chapter.title,
      chapter.summary,
      ...chapter.blocks.flatMap((block) => [block.title || "", block.text, block.prompt || ""])
    ].join(" ").toLocaleLowerCase().includes(needle));
  }
  complete(id, checked) {
    if (!this.steps.has(id))
      return;
    if (checked)
      this.checked.add(id);
    else
      this.checked.delete(id);
    this.save();
  }
  reset() {
    this.checked.clear();
    this.save();
  }
  index(id) {
    return Math.max(0, this.manual.chapters.findIndex((chapter) => chapter.id === id));
  }
  save() {
    try {
      this.store.write(this.key, { chapter: this.chapter.id, completed: this.completed });
    } catch {
      this.persistenceAvailable = false;
    }
  }
}
// ../../../the-factory/src/components/workflow-inspector/workflow-inspector.observed-attributes.ts
var workflow_inspector_observed_attributes_default = [];
// ../../../the-factory/src/components/workflow-phase/workflow-phase.observed-attributes.ts
var workflow_phase_observed_attributes_default = ["heading", "description", "status", "started", "ended"];

// ../../../the-factory/src/components/workflow-phase/index.ts
var workflowPhaseDefine = () => {
  if (!customElements.get("workflow-phase")) {
    customElements.define("workflow-phase", wrap(() => Promise.resolve().then(() => (init_workflow_phase_component(), exports_workflow_phase_component)), "WorkflowPhase", workflow_phase_observed_attributes_default));
  }
};

// ../../../the-factory/src/components/workflow-inspector/index.ts
var workflowInspectorDefine = () => {
  workflowPhaseDefine();
  if (!customElements.get("workflow-inspector")) {
    customElements.define("workflow-inspector", wrap(() => Promise.resolve().then(() => (init_workflow_inspector_component(), exports_workflow_inspector_component)), "WorkflowInspector", workflow_inspector_observed_attributes_default));
  }
};

// ../../../the-factory/src/components/workflow-inspector/session/inspection-session.ts
class InspectionSession {
  source;
  state = { status: "idle" };
  active;
  listeners = new Set;
  constructor(source) {
    this.source = source;
  }
  subscribe(listener) {
    this.listeners.add(listener);
    listener(this.state);
    return () => {
      this.listeners.delete(listener);
    };
  }
  async refresh(selected = "") {
    this.active?.abort();
    const request = new AbortController;
    this.active = request;
    this.publish({ status: "loading" });
    try {
      const checkpoint = await this.source.checkpoint(request.signal);
      if (request.signal.aborted)
        return;
      const id = selected || checkpoint.runs.at(-1);
      if (id && !checkpoint.runs.includes(id))
        throw new Error("That run is no longer in this assignment. Select Latest run and refresh.");
      const run = id ? await this.source.run(id, request.signal) : undefined;
      if (!request.signal.aborted)
        this.publish({ status: "ready", checkpoint, run, checkedAt: new Date().toISOString() });
    } catch (error) {
      if (!request.signal.aborted)
        this.publish({ status: "error", error: error instanceof Error ? error.message : "Evidence could not be read." });
    }
  }
  cancel() {
    this.active?.abort();
    this.publish({ status: "idle" });
  }
  publish(state) {
    this.state = state;
    for (const listener of this.listeners)
      listener(state);
  }
}

// src/architecture.ts
var architectureChapters = [
  {
    id: "web-components",
    title: "Learn the Web Components",
    summary: "Nine custom elements turn this manual into a reusable example from the-factory library.",
    blocks: [
      {
        kind: "text",
        text: "A Web Component gives a custom HTML element its own behavior and presentation. This manual uses the same @Component decorator and wrap() registration helper as the existing library. Each component has its own folder, TypeScript class, HTML template, observed attributes, index.ts, and styles/ directory."
      },
      { kind: "command", text: "<training-manual></training-manual>" },
      {
        kind: "text",
        text: "The second lesson adds workflow-inspector for read-only checkpoint and run inspection, and workflow-phase for each recorded phase. Neither component knows Toyota’s endpoint URLs. The app injects the evidence source through interfaces and provides its own link through a slot."
      },
      {
        kind: "text",
        text: "training-manual coordinates the page. manual-toc handles chapter links. manual-chapter presents a lesson. manual-progress displays practice progress. training-step supplies a reversible checkbox. command-example presents copyable text. training-callout highlights guidance or unfinished features."
      },
      {
        kind: "command",
        text: `<training-step step-id="inspect" heading="Inspect the receipt" text="Read the supporting facts.">
    <command-example example="Show me its supporting information."></command-example>
</training-step>`
      },
      {
        kind: "text",
        text: "Attributes carry simple values such as heading and completed. A slot places child content inside a component’s template. The shadow root keeps the template and styles local. Open browser Developer Tools → Elements and expand a custom element’s #shadow-root to inspect it."
      },
      {
        kind: "note",
        title: "Trace one interaction",
        text: "A checkbox emits manual-complete with its step ID and checked value. The event bubbles through the component boundary. The manual asks IManualSession to update reading progress, then refreshes the progress component. No financial endpoint participates."
      }
    ]
  },
  {
    id: "interfaces-and-patterns",
    title: "Interfaces and GoF patterns",
    summary: "An interface describes the job. The composition root chooses the object that performs it.",
    blocks: [
      {
        kind: "command",
        text: `interface IReadingStore {
    read( key: string ): unknown;
    write( key: string, checkpoint: IReadingCheckpoint ): void;
}`
      },
      {
        kind: "text",
        text: "ManualSession accepts IReadingStore. It does not import localStorage. BrowserReadingStore is an Adapter that satisfies this interface; tests inject an in-memory store or a failing store. The same session logic works with each implementation."
      },
      {
        kind: "text",
        text: "IChapterNavigation separates bookmarks and browser history from the manual. IClipboard separates copying from example presentation. IBlockRenderer and IBlockFactory separate a content block’s meaning from the Web Component used to display it."
      },
      {
        kind: "text",
        text: "Registry Factory: ManualBlockFactory selects a registered IBlockRenderer by kind. Composite: the manual contains chapters, and chapters contain blocks such as steps and callouts. Observer: components publish events; the manual reacts. Mediator: TrainingManual coordinates its components. Template Method: ManualComponent supplies the lifecycle contract while each component implements render()."
      },
      {
        kind: "command",
        text: `interface AssignmentPolicies {
    installed(): readonly string[];
    for_assignment( name: string ): AssignmentPolicy;
}`
      },
      {
        kind: "text",
        text: "Strategy registry: the same shape decides what Toyota will accept. On her side InstalledPolicies maps an assignment name to the policy that validates its requests; in the workflow it is AssignmentRegistry, which maps the same name to the Assignment that performs the work. An assignment is declared by being put in one of those maps at a composition root, and nowhere else."
      },
      {
        kind: "text",
        text: "Both registries refuse a name they do not hold, and the refusal lists what is installed instead of failing silently. The sentence Toyota speaks about which assignments exist is generated from installed(), so it cannot keep advertising something that was removed from the composition root. Today both maps hold one entry: tax_issues."
      },
      {
        kind: "note",
        title: "Where construction belongs",
        text: "dashboard/training/src/main.ts is the composition root. It chooses browser adapters and the block factory, then injects them through IManualDependencies. The library is under /home/adamsl/the-factory/src/components; ROL-specific lesson data stays in dashboard/training/src."
      },
      {
        kind: "text",
        text: "To add a chapter, add an IManualChapter to the content catalog with a stable, unique ID. The TOC, search, bookmark, and Previous/Next controls follow the catalog automatically. To add a new visual block, implement IBlockRenderer and register it with the factory. Write its tests before its implementation."
      },
      {
        kind: "command",
        text: `cd /home/adamsl/letta-code/dashboard/training
bun run test
bun run typecheck
bun run build
bun run test:browser`
      }
    ]
  }
];

// src/practice.ts
var practiceChapter = {
  id: "first-session",
  title: "Your first practice session",
  summary: "One synthetic expense, one category change, and a stored value you can check for yourself.",
  blocks: [
    {
      kind: "note",
      title: "Keep two tabs open",
      text: "Keep this manual open. Use “Open Toyota in another tab” above for the dashboard Home conversation. Keep that dashboard tab open while Toyota operates the editor. Send one request at a time and wait for its result. The sentences below are examples, not magic commands."
    },
    {
      kind: "step",
      id: "ask-capabilities",
      title: "1. Ask what Toyota can do",
      prompt: "What can you help me do with tax issues?",
      text: "She should describe the installed training operations: selecting the expense, opening supporting information and the editor, applying an explicit category, and checking progress. She should explain the training limitation."
    },
    {
      kind: "step",
      id: "start-assignment",
      title: "2. Choose the assignment",
      prompt: "Let’s work on tax issues.",
      text: "Look for “Toyota’s work — synthetic training”. Toyota is still your conversational coordinator; the assignment selects the workflow capabilities she uses."
    },
    {
      kind: "step",
      id: "select-expense",
      title: "3. Locate the practice expense",
      prompt: "Open expense #900001.",
      text: "Confirm #900001, $12.34, “Training pharmacy purchase”. This record lives in the separate rol_receptionist_training database. Its category may be RM or RJ depending on the last practice session."
    },
    {
      kind: "step",
      id: "inspect-evidence",
      title: "4. Open supporting information",
      prompt: "Show me its supporting information.",
      text: "A practice receipt should appear in Toyota’s browser area. Read the details before deciding what change to request."
    },
    {
      kind: "step",
      id: "open-editor",
      title: "5. Open the expense editor",
      prompt: "Open its expense editor.",
      text: "Check the record number and current category in the editor. The training flow reuses the application’s expense editor and validation."
    },
    {
      kind: "step",
      id: "save-category",
      title: "6. Request a specific category and verify it",
      prompt: "Change the category to Walgreens (RM).",
      text: "Watch the work panel while Toyota uses Save Changes and independently reloads the expense. Completion means the panel says “verified” and reports Walgreens (RM). If it already has RM, practice with “Change the category to Walgreens (RJ).” A promise to save is not verification."
    },
    {
      kind: "step",
      id: "resume-work",
      title: "7. Check that your place is retained",
      prompt: "Which expense are we working on, and what is its category?",
      text: "After the save is verified, refresh the dashboard and ask this question. Expect #900001 and the stored category. The assignment checkpoint should survive the refresh."
    },
    {
      kind: "note",
      title: "What the checkboxes mean",
      text: "“I tried this step” is your personal practice checklist. It never saves an expense or checks the database. Toyota’s work panel and its independent readback provide the actual save evidence."
    }
  ]
};

// src/recovery-practice.ts
var recoveryPracticeChapter = {
  id: "recovery-practice",
  title: "Your recovery practice session",
  summary: "Practise pausing, reloading, reconciling an interrupted save, cancelling, and retrying without saving twice.",
  blocks: [
    {
      kind: "note",
      title: "Do the first session before this one",
      text: "This session recovers a save, so it needs one that already happened. Finish “Your first practice session” first, so expense #900001 has a verified category to find your way back to. Everything here stays on the synthetic training record."
    },
    {
      kind: "step",
      id: "pause-work",
      title: "1. Pause in the middle of the work",
      prompt: "Pause this work.",
      text: "Pausing keeps your place instead of discarding it. The work panel should still name expense #900001 and the assignment. Nothing is written to the record when you pause."
    },
    {
      kind: "step",
      id: "resume-after-pause",
      title: "2. Ask where you left off",
      prompt: "Where did we leave off?",
      text: "Expect expense #900001 and its stored category. Toyota reads this from the retained checkpoint, so her answer should match what the editor last verified rather than what she last said."
    },
    {
      kind: "step",
      id: "reload-and-resume",
      title: "3. Reload the dashboard and resume",
      prompt: "Which expense are we working on, and what is its category?",
      text: "Refresh the dashboard tab, then ask this. The checkpoint lives on the server, not in the page, so a reload should lose nothing. If the work panel comes back empty, say so in your notes — that is a real failure, not a slow refresh."
    },
    {
      kind: "step",
      id: "reconcile-interrupted",
      title: "4. Reconcile an interrupted operation",
      prompt: "Change the category to Walgreens (RJ).",
      text: "Send the request, then refresh the dashboard while it is still working. When the panel returns it should offer “Check interrupted operation”. Use that button. It reads the stored record and tells you what actually happened; it never sends the save a second time. If the earlier save did land, this reports it as verified instead of writing a duplicate."
    },
    {
      kind: "step",
      id: "cancel-pending",
      title: "5. Cancel pending work",
      prompt: "Stop what you are doing.",
      text: "Cancelling stops anything still waiting. It does not undo a category that already saved — any earlier save is retained, and Toyota should say so plainly rather than claiming she put the record back."
    },
    {
      kind: "step",
      id: "safe-retry",
      title: "6. Retry safely",
      prompt: "What is the stored category for this expense right now?",
      text: "Read the stored value before asking for the change again. Request the save a second time only when the panel has not reported it as verified. Each request carries the version it expects to find, so a retry on an already-saved record reconciles with it instead of writing a duplicate."
    },
    {
      kind: "step",
      id: "confirm-single-save",
      title: "7. Confirm you saved only once",
      prompt: "Show me its supporting information.",
      text: "Reopen the record and check that the category is the one you asked for and that the untouched fields — description, date, amount, mileage, notes — are unchanged. One requested change should leave exactly one change behind."
    },
    {
      kind: "note",
      title: "Why there is no “crash it and see” step",
      text: "Recovery here is practised by reloading your own browser tab and by interrupting a request, never by stopping a shared service. Other people and agents use this machine, so breaking a service to make a demonstration would take their work down with it."
    }
  ]
};

// src/watch-a-run.ts
var watchARunChapter = {
  id: "watch-a-run",
  title: "Your second practice session",
  summary: "Watch Toyota’s checkpoint and compare the recorded phases before and after a request.",
  blocks: [
    {
      kind: "note",
      title: "Build on what you learned",
      text: "Toyota remembered your expense. Now learn how to inspect the work behind her replies. Keep Toyota’s Home conversation open in another tab. This lesson reads existing evidence; its Refresh button never starts an ADW, retries a save, or changes an expense."
    },
    {
      kind: "step",
      id: "inspect-checkpoint",
      title: "1. Read the checkpoint",
      text: "Click Refresh evidence below. Confirm the training environment and selected expense #900001. Note the latest run ID. The checkpoint is Toyota’s retained place in the workflow; it is separate from your manual checkboxes and is not a new database verification."
    },
    {
      kind: "workflow-evidence",
      text: "Read Toyota’s current checkpoint, choose an ADW run, and inspect its recorded phases."
    },
    {
      kind: "step",
      id: "watch-receipt-run",
      title: "2. Ask Toyota to open the supporting information",
      prompt: "Show me the supporting information for expense #900001.",
      text: "Send this in Toyota’s conversation and keep that tab open. Wait until her work panel says the supporting information opened. Return here and click Refresh evidence with Latest run selected. Compare the run ID with the one you noted."
    },
    {
      kind: "step",
      id: "compare-run-phases",
      title: "3. Inspect the phases and an earlier run",
      text: "Look for load_assignment, operate_tax_visit, and publish_checkpoint. Read the descriptions and timestamps. Choose an earlier run from ADW run to compare its evidence. One conversation request can produce more than one run: requesting browser work and acknowledging its result are separate operations. The current checkpoint remains current even when you select an older run."
    },
    {
      kind: "step",
      id: "watch-save-evidence",
      title: "4. Connect a category change to its evidence",
      prompt: "Change the category of expense #900001 to Walgreens (RM).",
      text: "Use the category flow you practiced in the first lesson. If the practice expense already has RM, explicitly request Walgreens (RJ) instead. Wait for Toyota’s verified stored-value result. Refresh this viewer, then inspect recent runs. The save run has validate_editor_request, save_through_expense_editor, verify_stored_expense, and publish_edit_evidence. The latest run may instead be the separate acknowledgement. Use the run picker and Open recorded events to inspect the actual evidence."
    },
    {
      kind: "note",
      title: "What the results mean",
      text: "Completed means a phase recorded success. It does not mean every action was an expense save. No completion recorded means no ending was present in the returned trace; it is not proof that work is still running. A failed read hides prior evidence until Refresh succeeds. This viewer does not automatically poll. Refresh after each request you want to inspect."
    },
    {
      kind: "text",
      text: "For Web Component practice, inspect <workflow-inspector> and its <workflow-phase> children in Developer Tools. The inspector receives IWorkflowInspector; its session receives IWorkflowEvidenceSource. The dashboard supplies a read-only Adapter over existing ADW routes. The manual’s block registry accepts this new renderer without adding workflow-specific logic to the manual shell."
    }
  ]
};

// src/work-panel.ts
var workPanelChapter = {
  id: "reading-the-work-panel",
  title: "Reading the work panel",
  summary: "Eight labelled rows, so waiting, stopped, failed and verified can never look alike.",
  blocks: [
    {
      kind: "text",
      text: "Toyota’s work panel sits under the conversation. It describes one piece of work at a time, using a separate labelled row for each question you would ask of it. Rows that have nothing to say are left out, so what you can see is what currently applies."
    },
    {
      kind: "text",
      text: "“Right now” is the one-line summary of the condition. “Assignment” is the job in progress, such as Tax issues. “Record” is the expense being worked on, such as Expense #900001. “Requested operation” is what was asked for in words — opening supporting information, opening the editor, or setting a category to a named value."
    },
    {
      kind: "text",
      text: "“Waiting for you” appears only when Toyota has asked a question and cannot continue until you answer it. “Problem” appears only for a failure or a cancellation. “Verified evidence” appears only when the stored value was read back out of the database. “Operation and run” names the operation ID and the ADW run the rest of the panel is describing."
    },
    {
      kind: "note",
      title: "Only one row is proof",
      text: "Verified evidence is the only row that reports a value read back from the database after the save. Every other row describes an intention or a condition. A reply that sounds finished, a requested operation, and a run ID are not confirmations. If Verified evidence is absent, treat the save as unconfirmed and check it."
    },
    {
      kind: "note",
      title: "Stopped is not undone",
      text: "Cancelling stops pending work. It does not undo a category that already saved — any earlier save is retained, and the Problem row says so rather than implying the record was put back. A failure is likewise honest that the stored value is not confirmed; it may have failed before or after the write, which is exactly why you re-read the record instead of guessing."
    },
    {
      kind: "text",
      text: "Above the rows there is still a plain status line in the server’s own words, such as “verified: Verified training expense #900001”. It is deliberately unchanged and unpolished: it shows exactly what the server said, so you can compare the explained rows against the raw source and notice if they ever disagree."
    },
    {
      kind: "text",
      text: "Everything in this lesson applies to practice expense #900001 in the separate training database. The panel marks its environment as training."
    },
    {
      kind: "command",
      text: `interface WorkPresenter {
    present( state: WorkState ): WorkFacts;
}`
    },
    {
      kind: "text",
      text: "Presenter: TrainingWorkPresenter turns one saved checkpoint into WorkFacts — the set of separate statements above — and the panel renders those statements without deciding anything. The rule that only a verified checkpoint produces an evidence line lives in the presenter, where it is covered by tests, instead of being re-decided wherever text happens to be written."
    },
    {
      kind: "text",
      text: "Because the panel depends on the WorkPresenter interface rather than on a particular presenter, a test can inject one that returns fixed WorkFacts, and a second assignment could later supply its own wording without touching the rendering. DashboardBrowserWorkspace receives the presenter at its composition root, in js/implementation/receptionist_work/src/composition.ts."
    },
    {
      kind: "placeholder",
      title: "Panel history and side-by-side runs",
      text: "{to_be_implemented} — the panel shows the most recent six history lines and the latest run only. Comparing two runs in the panel, and filtering its history, are not built."
    }
  ]
};

// src/content.ts
var trainingManual = {
  id: "rol-receptionist",
  version: 1,
  title: "ROL Finance training",
  chapters: [
    {
      id: "start-here",
      title: "Start here",
      summary: "A hands-on guide to Toyota, ADWs, and the components that make this manual work.",
      blocks: [
        {
          kind: "note",
          title: "Available now · synthetic training",
          text: "Toyota can work with practice expense #900001, open its receipt and editor, apply a category you specify, and verify the stored value. She can also build one practice report from the same training database, vendor spending by month, as a web page or a spreadsheet (CSV), and give you a link to it. This all uses the separate training database. She can also hand a request to the spreadsheet maker, which reads the real books (read-only) and builds a workbook for one category, or the built-in “Medical” group, with a comparison to last year, monthly pattern, and flags for possible duplicates and odd dates. Flags are for a person to review; nothing is changed. She can also summon her mechanic to diagnose or improve her own Python code (for example “implement the next voice enhancement for yourself”). The mechanic works on a sandbox copy, and a change is applied automatically only if every test passes, with no fewer tests than before and no protected files touched; she then restarts (offline about 30 seconds) and rolls back by herself if she does not come back. It cannot edit the dashboard. Real expense editing through the receptionist is still {to_be_implemented}."
        },
        {
          kind: "note",
          title: "Your next step",
          text: "Practice the tax lesson once end to end (Practice chapter), then ask Toyota for the practice spreadsheet: “Give me a spreadsheet of category spend by month.” If she refuses or loops, note her exact words and use Check interrupted operation. Then try the real one: “Make a spreadsheet of Medical for 2025 and compare it with last year.” The next build step is checking the flagged rows by hand and adding more named groups."
        },
        {
          kind: "text",
          text: "Use Contents to jump to a chapter. Search filters the chapter list using headings, explanations, and example commands. Previous chapter and Next chapter guide you through the full manual. The chapter in the URL can be bookmarked or shared."
        },
        {
          kind: "text",
          text: "Your reading position and practice checkmarks stay in this browser. They are separate from Toyota’s saved assignment. Reset practice checkmarks clears only the checklist. Copy example copies text; it never sends an instruction or executes a console command."
        },
        {
          kind: "text",
          text: "Start with “Your first practice session”. Later chapters explain ADWs, the console menu, recovery, Web Components, and interfaces. Features we have not built are explicitly marked {to_be_implemented}."
        },
        {
          kind: "link",
          text: "Open Toyota’s dashboard Home in another tab ↗",
          href: "/"
        }
      ]
    },
    practiceChapter,
    watchARunChapter,
    workPanelChapter,
    {
      id: "adws-phases-runs",
      title: "ADWs, phases, and runs",
      summary: "The workflow is the recipe. A phase is a named step. A run is one execution with evidence.",
      blocks: [
        {
          kind: "text",
          text: "An ADW is an AI Developer Workflow. It defines an operation as named phases. A phase can be ordinary code; it does not have to call a model. A run is one execution of an ADW, with its own ID, events, and results. One conversation can produce several runs."
        },
        {
          kind: "note",
          title: "Follow the evidence",
          text: "Use “Latest ADW run” in Toyota’s work panel to inspect a run. Its ID identifies that execution. A completed conversation reply does not by itself prove that a database change succeeded; the save flow also reads back the stored expense."
        },
        {
          kind: "text",
          text: "adw_receptionist_tax.py performs load_assignment → operate_tax_visit → publish_checkpoint. It restores the current assignment, performs a requested operation through shared interfaces, and retains the result. Browser actions may remain pending until the open dashboard carries them out."
        },
        {
          kind: "text",
          text: "adw_receptionist_edit.py performs validate_editor_request → save_through_expense_editor → verify_stored_expense → publish_edit_evidence. These are code phases. The editor applies normal validation and save behavior; the verification phase independently reloads the expense."
        },
        {
          kind: "text",
          text: "Toyota is the conversational coordinator. Tools perform bounded operations. An assignment determines the workflow in use. A specialist agent is useful for substantial independent analysis; a routine edit or navigation step can use a tool directly."
        }
      ]
    },
    {
      id: "console-menu",
      title: "The existing console menu",
      summary: "The console and receptionist reuse tax-review behavior, while their user interfaces differ.",
      blocks: [
        {
          kind: "command",
          text: `cd /home/adamsl/rol_finances
just tax-issues`
        },
        {
          kind: "text",
          text: "The justfile recipe is named tax-issues, with a hyphen. It invokes the resolver shown below. This is the existing real tax-review console, separate from the synthetic receptionist lesson. Copying this example does not execute it."
        },
        {
          kind: "command",
          text: `tax-issues:
    uv run adws/adw_resolve_tax_issues.py --config {{config}}`
        },
        {
          kind: "text",
          text: "The shared TaxReviewSession facade provides review questions, category eligibility, and supporting context. The receptionist invokes structured operations through application interfaces. Its training path does not type fixed menu numbers into a terminal."
        },
        {
          kind: "placeholder",
          title: "Interactive console control by Toyota",
          text: "{to_be_implemented} — general terminal sessions, prompt recognition, retained interactive input, and cancellation through the receptionist."
        }
      ]
    },
    {
      id: "voice-and-assignments",
      title: "Voice and assignments",
      summary: "Learn the workflow with text first, then use the dashboard’s existing voice input.",
      blocks: [
        {
          kind: "text",
          text: "The dashboard already has voice capture and a conversation path to Toyota. A spoken instruction must reach her as a transcript before she can act on it. For the first lesson, type the examples so you can inspect exactly what was requested. Then try the same requests through the existing voice controls and check the transcript."
        },
        {
          kind: "text",
          text: "“Let’s work on tax issues” selects the assignment without rewriting Toyota’s entire persona. The retained checkpoint includes the assignment, selected expense, progress, and unfinished browser operation. Keep the dashboard open while it processes browser work."
        },
        {
          kind: "note",
          title: "Use an exact requested change",
          text: "Say the expense number when choosing a record and the complete category name when changing it. If several records or categories could match, clarify the target. Toyota should ask rather than invent a record or a category."
        },
        {
          kind: "placeholder",
          title: "A complete voice-only lesson",
          text: "{to_be_implemented} — a tested voice-only walkthrough, including microphone setup, transcription correction, interruption, and recovery on each supported device."
        }
      ]
    },
    {
      id: "recovery",
      title: "Pause, resume, and recover",
      summary: "Use the retained checkpoint and stored evidence to decide what to do next.",
      blocks: [
        { kind: "command", text: "Pause this work." },
        {
          kind: "text",
          text: "Pause retains your place. To return, ask to work on tax issues and ask where you left off. Cancellation stops pending work, but it does not undo a category that was already saved."
        },
        { kind: "command", text: "Where did we leave off?" },
        {
          kind: "note",
          title: "After a stalled or interrupted save",
          text: "Read Toyota’s work panel. If offered, use “Check interrupted operation” to reconcile the saved result before repeating the request. Do not assume that a lost reply means the save failed. Report success only when the stored value is verified."
        },
        {
          kind: "text",
          text: "If Toyota describes only her old analyst roster, refresh the dashboard and ask what she can do with tax issues. The operational training path needs the receptionist-team service. If that service is unavailable, the fallback conversation does not gain these operations automatically."
        }
      ]
    },
    recoveryPracticeChapter,
    ...architectureChapters,
    {
      id: "coming-next",
      title: "What is coming next",
      summary: "The following capabilities are planned. They are not instructions you can complete today.",
      blocks: [
        {
          kind: "placeholder",
          title: "Real expense assignments",
          text: "{to_be_implemented} — move the verified training interaction to explicitly selected real records."
        },
        {
          kind: "placeholder",
          title: "Additional assignments",
          text: "{to_be_implemented} — assignments beyond tax issues and the practice report, such as further real-books reports beyond the category spreadsheet, including switching away and restoring unfinished work."
        },
        {
          kind: "placeholder",
          title: "General browser operations",
          text: "{to_be_implemented} — arbitrary pages, selected sections, and additional requested expense fields beyond this category lesson."
        },
        {
          kind: "placeholder",
          title: "File and console operations",
          text: "{to_be_implemented} — receptionist file searches, opening results, and maintained interactive terminal sessions."
        },
        {
          kind: "placeholder",
          title: "Voice training across devices",
          text: "{to_be_implemented} — device-specific voice lessons and verified recovery after speech interruptions."
        }
      ]
    }
  ]
};

// src/evidence/decoders.ts
var invalid = () => {
  throw new Error("The server returned invalid workflow evidence. Refresh to retry.");
};
var record = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : invalid();
var string = (value) => typeof value === "string" ? value : invalid();
var runId = (value) => /^[a-f0-9]{8}$/.test(string(value)) ? value : invalid();
function decodeCheckpoint(value) {
  const response = record(value);
  if (response.ok !== true)
    invalid();
  const state = record(response.state);
  if (state.expense_id !== null && (!Number.isSafeInteger(state.expense_id) || state.expense_id <= 0))
    invalid();
  if (!Array.isArray(state.run_ids))
    invalid();
  return {
    assignment: string(state.assignment),
    environment: string(state.environment),
    status: string(state.status),
    expense: state.expense_id,
    category: string(state.category),
    message: string(state.message),
    pending: state.command === null ? null : string(record(state.command).action),
    runs: [...new Set(state.run_ids.map(runId))]
  };
}
function decodeRun(value, expected) {
  const response = record(value);
  if (response.ok !== true || runId(response.run_id) !== expected || !Array.isArray(response.events))
    invalid();
  const events = response.events;
  const phases = new Map;
  let recordedAt = "";
  for (const raw of events) {
    const event = record(raw);
    if (event.adw_id !== expected)
      invalid();
    const type = string(event.type);
    const timestamp = string(event.ts);
    if (!Number.isFinite(Date.parse(timestamp)))
      invalid();
    recordedAt = timestamp;
    if (type !== "phase_start" && type !== "phase_end")
      continue;
    const id = string(event.phase_id);
    if (!id)
      invalid();
    const name = string(event.name);
    const payload = record(event.payload);
    const previous = phases.get(id);
    if (type === "phase_start") {
      phases.set(id, {
        id,
        name,
        description: typeof payload.description === "string" ? payload.description : "",
        status: "No completion recorded",
        started: timestamp,
        ended: ""
      });
    } else {
      const status = payload.status === "success" ? "Completed" : ["error", "failed", "failure"].includes(String(payload.status)) ? "Failed" : "Unknown result";
      phases.set(id, {
        id,
        name,
        description: previous?.description || "",
        status,
        started: previous?.started || "",
        ended: timestamp
      });
    }
  }
  return {
    id: expected,
    phases: [...phases.values()],
    recordedAt,
    limited: events.length >= 500
  };
}

// src/evidence/receptionist-evidence.ts
class ReceptionistEvidenceSource {
  constructor(http) {
    this.http = http;
  }
  async checkpoint(signal) {
    return decodeCheckpoint(await this.http.get("/api/receptionist-work", {
      method: "GET",
      cache: "no-store",
      signal
    }));
  }
  async run(id, signal) {
    const checked = runId(id);
    return decodeRun(await this.http.get(`/api/receptionist-work/trace?run=${checked}`, {
      method: "GET",
      cache: "no-store",
      signal
    }), checked);
  }
}

class BrowserReadJson {
  async get(url, options) {
    const controller = new AbortController;
    const abort = () => controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    if (options.signal?.aborted)
      abort();
    const timeout = setTimeout(abort, 15000);
    try {
      const response = await fetch(url, {
        ...options,
        method: "GET",
        signal: controller.signal
      });
      if (!response.ok)
        throw new Error(`Evidence unavailable (HTTP ${response.status}). Refresh to retry.`);
      return await response.json();
    } catch (error) {
      if (controller.signal.aborted)
        throw new Error("Evidence request stopped or timed out. Refresh to retry.");
      throw error;
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}

// src/evidence/renderer.ts
class WorkflowEvidenceRenderer {
  constructor(document2, createInspector) {
    this.document = document2;
    this.createInspector = createInspector;
  }
  create(_block) {
    const element = this.document.createElement("workflow-inspector");
    const link = this.document.createElement("a");
    link.slot = "run-link";
    link.textContent = "Open recorded events";
    link.target = "_blank";
    link.rel = "noopener";
    link.hidden = true;
    element.append(link);
    element.addEventListener("ready", () => element.initialize(this.createInspector()), { once: true });
    element.addEventListener("workflow-run-selected", (event) => {
      const id = event.detail.id;
      link.hidden = !/^[a-f0-9]{8}$/.test(id);
      if (!link.hidden)
        link.href = `/receptionist_training.html?trace=${id}`;
      else
        link.removeAttribute("href");
    });
    return element;
  }
}

// src/main.ts
var host = document.querySelector("training-manual");
host.addEventListener("ready", () => {
  try {
    const navigation = new HashChapterNavigation(window);
    host.initialize({
      manual: trainingManual,
      session: new ManualSession(trainingManual, new BrowserReadingStore(window), navigation.current()),
      navigation,
      clipboard: new BrowserClipboard(navigator),
      blocks: createDefaultBlockFactory(document, new Map([
        [
          "workflow-evidence",
          new WorkflowEvidenceRenderer(document, () => new InspectionSession(new ReceptionistEvidenceSource(new BrowserReadJson)))
        ]
      ]))
    });
    document.getElementById("loading").hidden = true;
  } catch (error) {
    document.getElementById("loading").textContent = `The manual could not open: ${String(error)}. Refresh to retry.`;
  }
}, { once: true });
workflowInspectorDefine();
trainingManualDefine();
