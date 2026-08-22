export const AMAZON_MARKETPLACE_KEY = "amazon-marketplace";

export const WORKFLOW_EVENTS = Object.freeze({
  start: "rol:report-workflow-start",
  step: "rol:report-workflow-step",
  complete: "rol:report-workflow-complete",
  cancel: "rol:report-workflow-cancel",
});

export const AMAZON_REPORT_STEPS = Object.freeze([
  { label: "Read the Amazon workbook", actors: [0, 1], message: 0 },
  { label: "Parse each order", actors: [1], message: 1 },
  { label: "Create AmazonMarketplaceExpense", actors: [1, 2], message: 2 },
  {
    label: "Confirm workbook order and item totals",
    actors: [0, 1, 2],
    note: 0,
  },
  { label: "Return extracted expense objects", actors: [1, 3], message: 3 },
  { label: "Map to StoredAmazonExpense", actors: [3, 4], message: 4 },
  { label: "Send expenses to the repository", actors: [3, 5], message: 5 },
  { label: "Insert standalone expense rows", actors: [5, 6], message: 6 },
  { label: "Confirm standalone identity policy", actors: [5, 6], note: 1 },
  { label: "Load persisted rows for verification", actors: [6, 7], message: 7 },
  { label: "Load source orders for verification", actors: [0, 7], message: 8 },
  { label: "Reconcile order totals", actors: [7], message: 9 },
  { label: "Check duplicate and vendor keys", actors: [7], message: 10 },
  { label: "Check Amazon reporting category", actors: [7], message: 11 },
  { label: "Check receipt metadata and PASS status", actors: [7], message: 12 },
  { label: "Write the verified report", actors: [7, 8], message: 13 },
  {
    label: "Save report.html in the January directory",
    actors: [8, 7],
    message: 14,
  },
  { label: "Expose report.html in the dashboard", actors: [8, 7], message: 15 },
]);

const numberAttr = (element, name) =>
  Number.parseFloat(element?.getAttribute?.(name) || "0") || 0;

const pathY = (path) => {
  const match = String(path?.getAttribute?.("d") || "").match(
    /^M\s*[-.\d]+[, ]+([-.\d]+)/,
  );
  return match ? Number.parseFloat(match[1]) : 0;
};

const verticalPosition = (element) =>
  numberAttr(element, "y1") || numberAttr(element, "y") || pathY(element);

const sortedByPosition = (elements, axis = "x") =>
  [...elements].sort(
    (left, right) => numberAttr(left, axis) - numberAttr(right, axis),
  );

function messageTextGroups(svg, messageLines) {
  const texts = sortedByPosition(svg.querySelectorAll(".messageText"), "y");
  let previousLineY = 0;
  return messageLines.map((line) => {
    const currentLineY = verticalPosition(line);
    const group = texts.filter((text) => {
      const y = verticalPosition(text);
      return y > previousLineY && y < currentLineY;
    });
    previousLineY = currentLineY;
    return group;
  });
}

function actorRectangles(svg) {
  const top = sortedByPosition(svg.querySelectorAll("rect.actor-top"));
  const bottom = sortedByPosition(svg.querySelectorAll("rect.actor-bottom"));
  return top.map((actor, index) => [actor, bottom[index]].filter(Boolean));
}

function mark(elements) {
  for (const element of elements || [])
    element.classList.add("workflow-active");
}

export function clearAmazonWorkflowFrame(svg) {
  svg.querySelectorAll(".workflow-active").forEach((element) => {
    element.classList.remove("workflow-active");
  });
}

export function paintAmazonWorkflowFrame(svg, step) {
  clearAmazonWorkflowFrame(svg);
  if (!step) return;

  const actors = actorRectangles(svg);
  for (const actorIndex of step.actors || []) mark(actors[actorIndex]);

  if (Number.isInteger(step.message)) {
    const lines = [
      ...svg.querySelectorAll(".messageLine0, .messageLine1"),
    ].sort((left, right) => verticalPosition(left) - verticalPosition(right));
    const textGroups = messageTextGroups(svg, lines);
    mark([lines[step.message]]);
    mark(textGroups[step.message]);
  }

  if (Number.isInteger(step.note)) {
    const noteRects = sortedByPosition(svg.querySelectorAll("rect.note"), "y");
    const noteRect = noteRects[step.note];
    mark([noteRect]);
    if (noteRect) {
      const top = numberAttr(noteRect, "y");
      const bottom = top + numberAttr(noteRect, "height");
      mark(
        [...svg.querySelectorAll(".noteText")].filter((text) => {
          const y = verticalPosition(text);
          return y >= top && y <= bottom;
        }),
      );
    }
  }
}

export class ReportWorkflowAnimator {
  constructor({
    steps = AMAZON_REPORT_STEPS,
    frameMs = 650,
    emit,
    wait = (milliseconds) =>
      new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds)),
  } = {}) {
    this.steps = steps;
    this.frameMs = frameMs;
    this.emit = emit || (() => {});
    this.wait = wait;
    this._run = 0;
  }

  cancel() {
    this._run += 1;
    this.emit(WORKFLOW_EVENTS.cancel, {});
  }

  async play() {
    const run = ++this._run;
    this.emit(WORKFLOW_EVENTS.start, { total: this.steps.length });
    for (let index = 0; index < this.steps.length; index += 1) {
      if (run !== this._run) return false;
      this.emit(WORKFLOW_EVENTS.step, {
        index,
        total: this.steps.length,
        step: this.steps[index],
      });
      await this.wait(this.frameMs);
    }
    if (run !== this._run) return false;
    this.emit(WORKFLOW_EVENTS.complete, { total: this.steps.length });
    return true;
  }
}

export async function loadJanuaryReportOptions(fetcher = globalThis.fetch) {
  const response = await fetcher("/api/rol-finance-reports?month=jan-2025");
  if (!response.ok)
    throw new Error(`Report catalog request failed: ${response.status}`);
  return response.json();
}
