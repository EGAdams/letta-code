import { STATUS_LABELS } from "./interface-spec.js";

/**
 * InterfacePageRenderer — turns one InterfaceSpec into the eight sections every
 * interface tab shares.
 *
 * The section order is fixed on purpose: whichever interface you open, the
 * answer to "what is done and what should I build next" is always in the same
 * place. Adding an interface never means writing markup.
 *
 * The Mermaid view is injected so this class has no knowledge of diagram
 * rendering beyond "hand the diagram to something that can draw it".
 */
export class InterfacePageRenderer {
  constructor({ mermaidView = null, doc = globalThis.document } = {}) {
    this._mermaid = mermaidView;
    this._doc = doc;
  }

  _el(tag, className, props = {}) {
    const el = this._doc.createElement(tag);
    if (className) el.className = className;
    Object.assign(el, props);
    return el;
  }

  _section(parent, heading, className = "") {
    const section = this._el("section", `spec-section ${className}`.trim());
    section.append(this._el("h2", null, { textContent: heading }));
    parent.append(section);
    return section;
  }

  _list(parent, items, className = "") {
    if (!items?.length) return null;
    const ul = this._el("ul", className);
    for (const item of items)
      ul.append(this._el("li", null, { textContent: item }));
    parent.append(ul);
    return ul;
  }

  /**
   * Render `spec` into `container` (which is emptied first).
   * @returns {Promise<Element>} the container
   */
  async render(container, spec) {
    container.innerHTML = "";
    this._renderHeader(container, spec);
    this._renderResponsibility(container, spec);
    await this._renderDiagrams(container, spec, 0, 1);
    this._renderContract(container, spec);
    this._renderImplementations(container, spec);
    this._renderDependencies(container, spec);
    await this._renderDiagrams(container, spec, 1);
    this._renderDevelopmentStatus(container, spec);
    this._renderTests(container, spec);
    this._renderNextWork(container, spec);
    return container;
  }

  _renderHeader(parent, spec) {
    const header = this._el("header", "spec-header");
    header.append(this._el("h1", null, { textContent: spec.name }));
    if (spec.tagline)
      header.append(
        this._el("p", "spec-tagline", { textContent: spec.tagline }),
      );
    const pill = this._el("span", `pill status-${spec.status}`, {
      textContent: STATUS_LABELS[spec.status],
    });
    const row = this._el("p", "spec-status-row");
    row.append(pill);
    if (spec.statusNote)
      row.append(
        this._el("span", "spec-status-note", { textContent: spec.statusNote }),
      );
    header.append(row);

    if (spec.links?.length) {
      const links = this._el("p", "spec-links");
      for (const link of spec.links) {
        const a = this._el("a", null, {
          href: link.href,
          textContent: link.label,
        });
        a.target = "_blank";
        a.rel = "noopener";
        links.append(a);
      }
      header.append(links);
    }
    parent.append(header);
  }

  _renderResponsibility(parent, spec) {
    const section = this._section(parent, "1 · Responsibility");
    for (const para of spec.responsibility)
      section.append(this._el("p", null, { textContent: para }));
  }

  _renderContract(parent, spec) {
    if (!spec.contract) return;
    const section = this._section(parent, "2 · Contract");
    const pre = this._el("pre");
    pre.append(
      this._el("code", spec.contract.language || null, {
        textContent: spec.contract.code.trim(),
      }),
    );
    section.append(pre);
    if (spec.contract.note)
      section.append(
        this._el("p", "note", { textContent: spec.contract.note }),
      );
  }

  _renderImplementations(parent, spec) {
    if (!spec.implementations?.length) return;
    const section = this._section(parent, "3 · Implementations");
    const groups = [
      ["current", "Current"],
      ["planned", "Planned"],
      ["deprecated", "Deprecated / superseded"],
    ];
    for (const [kind, label] of groups) {
      const items = spec.implementations.filter((i) => i.kind === kind);
      if (!items.length) continue;
      section.append(this._el("h3", null, { textContent: label }));
      const table = this._el("table", "impl-table");
      const tbody = this._el("tbody");
      for (const impl of items) {
        const tr = this._el("tr", `impl-${kind}`);
        const nameCell = this._el("td", "impl-name");
        nameCell.append(this._el("code", null, { textContent: impl.name }));
        tr.append(nameCell);
        tr.append(
          this._el("td", "impl-file", { textContent: impl.file || "—" }),
        );
        tr.append(
          this._el("td", "impl-note", { textContent: impl.note || "" }),
        );
        tbody.append(tr);
      }
      table.append(tbody);
      section.append(table);
    }
  }

  _renderDependencies(parent, spec) {
    if (!spec.dependencies) return;
    const section = this._section(parent, "4 · Dependencies");
    const { dependsOn, usedBy, note } = spec.dependencies;
    if (usedBy?.length) {
      section.append(
        this._el("h3", null, {
          textContent: "Depended on by (high-level policy)",
        }),
      );
      this._list(section, usedBy);
    }
    if (dependsOn?.length) {
      section.append(this._el("h3", null, { textContent: "Depends on" }));
      this._list(section, dependsOn);
    }
    if (note) section.append(this._el("p", "note", { textContent: note }));
  }

  // Sections 5 and 6 always render, even when empty. This page exists to answer
  // "what is done and what is protected"; quietly omitting either heading would
  // make an undocumented interface look the same as a complete one.
  _renderDevelopmentStatus(parent, spec) {
    const section = this._section(
      parent,
      "5 · Development status",
      "status-section",
    );
    const { done, gaps } = spec.developmentStatus || {};
    if (!done?.length && !gaps?.length) {
      section.append(
        this._el("p", "note", {
          textContent: "Development status has not been recorded yet.",
        }),
      );
      return;
    }
    if (done?.length) {
      const box = this._el("div", "box good");
      box.append(this._el("div", "h", { textContent: "Done" }));
      this._list(box, done);
      section.append(box);
    }
    if (gaps?.length) {
      const box = this._el("div", "box warn");
      box.append(this._el("div", "h", { textContent: "Needs work" }));
      this._list(box, gaps);
      section.append(box);
    }
  }

  _renderTests(parent, spec) {
    const section = this._section(parent, "6 · Tests");
    const { files, untested, next } = spec.tests || {};
    if (files?.length) {
      const table = this._el("table", "test-table");
      const thead = this._el("thead");
      const hrow = this._el("tr");
      for (const h of ["Test file", "Cases", "What it proves"])
        hrow.append(this._el("th", null, { textContent: h }));
      thead.append(hrow);
      const tbody = this._el("tbody");
      for (const file of files) {
        const tr = this._el("tr");
        const pathCell = this._el("td");
        pathCell.append(this._el("code", null, { textContent: file.path }));
        tr.append(pathCell);
        tr.append(
          this._el("td", "num", {
            textContent: file.count == null ? "—" : String(file.count),
          }),
        );
        tr.append(this._el("td", null, { textContent: file.proves }));
        tbody.append(tr);
      }
      table.append(thead, tbody);
      section.append(table);
    } else {
      section.append(
        this._el("p", "note", {
          textContent: "No tests exist for this interface yet.",
        }),
      );
    }
    if (untested?.length) {
      const box = this._el("div", "box bad");
      box.append(
        this._el("div", "h", { textContent: "Not protected by any test" }),
      );
      this._list(box, untested);
      section.append(box);
    }
    if (next?.length) {
      section.append(this._el("h3", null, { textContent: "Write next" }));
      this._list(section, next, "ordered-ish");
    }
  }

  async _renderDiagrams(parent, spec, from, to) {
    if (!this._mermaid || !spec.diagrams?.length) return;
    const slice = spec.diagrams.slice(from, to);
    if (!slice.length) return;
    const section = this._el("section", "spec-section diagrams");
    parent.append(section);
    for (const diagram of slice) await this._mermaid.render(section, diagram);
  }

  _renderNextWork(parent, spec) {
    if (!spec.nextWork?.length) return;
    const section = this._section(parent, "7 · Next work", "next-work");
    const ol = this._el("ol");
    for (const item of spec.nextWork)
      ol.append(this._el("li", null, { textContent: item }));
    section.append(ol);
  }
}
