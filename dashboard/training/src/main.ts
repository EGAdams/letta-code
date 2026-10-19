import { trainingManualDefine } from "../../../../the-factory/src/components/training-manual";
import {
  BrowserClipboard,
  BrowserReadingStore,
  HashChapterNavigation,
} from "../../../../the-factory/src/components/training-manual/adapters/browser-ports";
import { createDefaultBlockFactory } from "../../../../the-factory/src/components/training-manual/factory/block-factory";
import type { IManualElement } from "../../../../the-factory/src/components/training-manual/interfaces";
import { ManualSession } from "../../../../the-factory/src/components/training-manual/session/manual-session";
import { workflowInspectorDefine } from "../../../../the-factory/src/components/workflow-inspector";
import { InspectionSession } from "../../../../the-factory/src/components/workflow-inspector/session/inspection-session";
import { trainingManual } from "./content";
import {
  BrowserReadJson,
  ReceptionistEvidenceSource,
} from "./evidence/receptionist-evidence";
import { WorkflowEvidenceRenderer } from "./evidence/renderer";

// Composition root: the only place that selects concrete browser adapters.
const host = document.querySelector<IManualElement>("training-manual")!;
host.addEventListener(
  "ready",
  () => {
    try {
      const navigation = new HashChapterNavigation(window);
      host.initialize({
        manual: trainingManual,
        session: new ManualSession(
          trainingManual,
          new BrowserReadingStore(window),
          navigation.current(),
        ),
        navigation: navigation,
        clipboard: new BrowserClipboard(navigator),
        blocks: createDefaultBlockFactory(
          document,
          new Map([
            [
              "workflow-evidence",
              new WorkflowEvidenceRenderer(
                document,
                () =>
                  new InspectionSession(
                    new ReceptionistEvidenceSource(new BrowserReadJson()),
                  ),
              ),
            ],
          ]),
        ),
      });
      document.getElementById("loading")!.hidden = true;
    } catch (error) {
      document.getElementById("loading")!.textContent =
        `The manual could not open: ${String(error)}. Refresh to retry.`;
    }
  },
  { once: true },
);
workflowInspectorDefine();
trainingManualDefine();
