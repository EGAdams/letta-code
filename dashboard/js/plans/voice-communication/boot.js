import { InterfacePageRenderer } from "../interface-page.js";
import { InterfaceWorkspace } from "../interface-workspace.js";
import { MermaidView } from "../mermaid-view.js";
import { voiceCommunicationSpecs } from "./index.js";

/**
 * Composition root for the Voice Communication workspace.
 *
 * The only place the CDN globals (mermaid, svgPanZoom) are read. Everything
 * above this file takes them as injected collaborators, which is what keeps the
 * workspace unit-testable under Bun with no browser.
 */
const mermaidView = new MermaidView({
  mermaid: globalThis.mermaid,
  svgPanZoom: globalThis.svgPanZoom,
});

const workspace = new InterfaceWorkspace({
  specs: voiceCommunicationSpecs,
  pageRenderer: new InterfacePageRenderer({ mermaidView }),
  mermaidView,
});

// Mount immediately so the nav is present and the iframe finishes loading even
// while the Project Plans tab is still hidden. MermaidView defers each diagram
// until the document actually has layout — a hidden `.view` measures as zero
// width, and Mermaid turns that into a bogus "Syntax error in text".
workspace.mount("workspace-nav", "workspace-content");
