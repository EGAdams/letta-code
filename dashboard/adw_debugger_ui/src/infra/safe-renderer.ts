// ISequenceDiagramRenderer: checks a model before it reaches the component, and
// hands back the last good one when a model cannot be drawn.
import type {
  DiagramModel,
  ISequenceDiagramRenderer,
  RenderResult,
} from "../contracts";

export class LastGoodDiagramRenderer implements ISequenceDiagramRenderer {
  private lastGood: DiagramModel = { runId: "", columns: [], rows: [] };

  render(model: DiagramModel): RenderResult {
    try {
      const ids = new Set<string>();
      for (const column of model.columns) {
        if (!column.instanceId || ids.has(column.instanceId)) {
          throw new Error(
            `duplicate or empty phase instance id "${column.instanceId}"`,
          );
        }
        ids.add(column.instanceId);
      }
      for (const row of model.rows) {
        if (!model.columns[row.from] || !model.columns[row.to]) {
          throw new Error(
            `arrow ${row.id} points at a column that is not on screen`,
          );
        }
      }
      this.lastGood = model;
      return { model, error: "" };
    } catch (error) {
      return {
        model: this.lastGood,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }
}
