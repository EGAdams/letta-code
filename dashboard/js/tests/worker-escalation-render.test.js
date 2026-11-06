import { expect, test } from "bun:test";
import { renderWorkerEscalation } from "../abstract/worker-escalation-render.js";

test("missing and stale telemetry never render a healthy verdict", () => {
  expect(renderWorkerEscalation({})).toContain("telemetry unavailable");
  const html = renderWorkerEscalation({
    escalation: { available: true, stale: true, ok: true, alerts: [] },
  });
  expect(html).toContain("heartbeat is stale");
  expect(html).not.toContain("No escalations in observed");
});

test("shows escaped per-task recommendations and incomplete coverage", () => {
  const html = renderWorkerEscalation({
    escalation: {
      available: true,
      ok: true,
      coverage_complete: false,
      coverage_reason: "Gateway queue is not visible",
      alerts: [
        {
          task_id: "t_<x>",
          tier: "diagnose",
          recent_events: [{ message: "Inspect <script>" }],
        },
      ],
    },
  });
  expect(html).toContain("Gateway queue is not visible");
  expect(html).toContain("coverage_complete: false");
  expect(html).toContain("t_&lt;x&gt;");
  expect(html).toContain("Inspect &lt;script&gt;");
  expect(html).not.toContain("<script>");
});
