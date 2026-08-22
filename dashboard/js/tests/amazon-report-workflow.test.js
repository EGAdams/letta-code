import { describe, expect, test } from "bun:test";
import {
  AMAZON_REPORT_STEPS,
  loadJanuaryReportOptions,
  ReportWorkflowAnimator,
  WORKFLOW_EVENTS,
} from "../plans/process-flows/amazon-report-workflow.js";

describe("Amazon report workflow", () => {
  test("defines one readable frame for every message and verification note", () => {
    expect(AMAZON_REPORT_STEPS.length).toBe(18);
    expect(
      AMAZON_REPORT_STEPS.filter((step) => Number.isInteger(step.message))
        .length,
    ).toBe(16);
    expect(
      AMAZON_REPORT_STEPS.filter((step) => Number.isInteger(step.note)).length,
    ).toBe(2);
    expect(AMAZON_REPORT_STEPS.at(-1).label).toContain("dashboard");
  });

  test("emits start, every frame in order, and complete", async () => {
    const events = [];
    const animator = new ReportWorkflowAnimator({
      steps: AMAZON_REPORT_STEPS.slice(0, 3),
      emit: (type, detail) => events.push({ type, detail }),
      wait: async () => {},
    });
    expect(await animator.play()).toBe(true);
    expect(events.map((event) => event.type)).toEqual([
      WORKFLOW_EVENTS.start,
      WORKFLOW_EVENTS.step,
      WORKFLOW_EVENTS.step,
      WORKFLOW_EVENTS.step,
      WORKFLOW_EVENTS.complete,
    ]);
    expect(events[2].detail.index).toBe(1);
  });

  test("loads the dropdown from the January Reports endpoint", async () => {
    let requested = "";
    const reports = await loadJanuaryReportOptions(async (url) => {
      requested = url;
      return {
        ok: true,
        async json() {
          return [{ key: "amazon-marketplace", label: "Amazon Marketplace" }];
        },
      };
    });
    expect(requested).toBe("/api/rol-finance-reports?month=jan-2025");
    expect(reports[0].label).toBe("Amazon Marketplace");
  });
});
