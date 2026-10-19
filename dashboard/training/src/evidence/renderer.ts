import type {
  IBlockRenderer,
  IManualBlock,
} from "../../../../../the-factory/src/components/training-manual/interfaces";
import type {
  IWorkflowInspector,
  IWorkflowInspectorElement,
} from "../../../../../the-factory/src/components/workflow-inspector/interfaces";

/** Renderer Strategy: app links belong here, outside the reusable inspector. */
export class WorkflowEvidenceRenderer implements IBlockRenderer {
  constructor(
    private readonly document: Document,
    private readonly createInspector: () => IWorkflowInspector,
  ) {}
  create(_block: IManualBlock): HTMLElement {
    const element = this.document.createElement(
      "workflow-inspector",
    ) as IWorkflowInspectorElement;
    const link = this.document.createElement("a");
    link.slot = "run-link";
    link.textContent = "Open recorded events";
    link.target = "_blank";
    link.rel = "noopener";
    link.hidden = true;
    element.append(link);
    element.addEventListener(
      "ready",
      () => element.initialize(this.createInspector()),
      { once: true },
    );
    element.addEventListener("workflow-run-selected", (event) => {
      const id = (event as CustomEvent<{ id: string }>).detail.id;
      link.hidden = !/^[a-f0-9]{8}$/.test(id);
      if (!link.hidden) link.href = `/receptionist_training.html?trace=${id}`;
      else link.removeAttribute("href");
    });
    return element;
  }
}
