import { expect, test } from "bun:test";
import { renderWorkerRequests } from "../abstract/worker-requests-render.js";

test("unavailable supervision is never shown as no requests", () => {
  const html = renderWorkerRequests({
    requests: { available: false, reason: "no worker token on this machine" },
  });
  expect(html).toContain("no worker token");
  expect(html).toContain("not known to be clear");
  expect(html).not.toContain("No open requests");
  expect(renderWorkerRequests({})).toContain("unavailable");
});

test("a blocked deed request shows its blocker, owner, timer, deliverables and escaped text", () => {
  const html = renderWorkerRequests({
    requests: {
      available: true,
      watch: { checked_seconds_ago: 42, refresh_seconds: 30 },
      thresholds: {
        accept_seconds: 30,
        progress_seconds: 120,
        warn_seconds: 300,
        escalate_seconds: 600,
      },
      open: [
        {
          request_id: "rq_1",
          title: "Print the final deed <b>",
          client: "chatgpt-bridge",
          phase: "blocked",
          timer: "escalated",
          since_progress: "12 min",
          responsible: "EG",
          blocked_on: "Both documents are still drafts",
          blocked_owner: "EG",
          deliverables: [
            { key: "d1", label: "print the deed", status: "missing" },
          ],
          pending: ["the deed PDF is not in the print outbox"],
          child_tasks: [
            {
              task_id: "t_1",
              operation: "print_discover",
              state: "succeeded",
              status_check: true,
            },
          ],
          escalations: [{ event: "warning" }, { event: "escalated" }],
          recovery_attempts: 0,
        },
      ],
      recently_closed: [
        { title: "Scan", state: "cancelled", outcome: "cancelled" },
      ],
    },
  });
  expect(html).toContain("Print the final deed &lt;b&gt;");
  expect(html).toContain(
    "Blocked on: Both documents are still drafts — owner EG",
  );
  expect(html).toContain("ESCALATED");
  expect(html).toContain("am-bad");
  expect(html).toContain("print the deed: <strong>missing</strong>");
  expect(html).toContain("t_1 print_discover <em>succeeded</em> (check)");
  expect(html).toContain("2 escalation event(s)");
  expect(html).toContain("last checked 42 s ago");
  expect(html).toContain("not proof paper came out");
  expect(html).toContain("Closed in the last day (1)");
});

test("a late gateway watch is flagged", () => {
  const html = renderWorkerRequests({
    requests: {
      available: true,
      open: [],
      watch: { checked_seconds_ago: 900 },
    },
  });
  expect(html).toContain("later than expected");
  expect(html).toContain("No open requests on the gateway.");
});
