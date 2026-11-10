import { expect, test } from "bun:test";
import { parseGatewayRequests } from "../abstract/monitors/sources/parsers/gateway-requests-parser.js";

test("unreadable supervision is unknown, not ok", () => {
  expect(parseGatewayRequests({}).level).toBe("unknown");
  expect(
    parseGatewayRequests({ requests: { available: false, reason: "no token" } })
      .detail,
  ).toBe("no token");
});

test("an escalated request is critical and a blocked one warns", () => {
  const s = parseGatewayRequests({
    requests: {
      available: true,
      watch: { checked_seconds_ago: 20 },
      open: [
        {
          request_id: "rq_1",
          title: "Print deed",
          phase: "blocked",
          timer: "ok",
          blocked_on: "drafts",
        },
        {
          request_id: "rq_2",
          title: "Scan",
          phase: "running",
          timer: "escalated",
          since_progress: "11 min",
        },
      ],
    },
  });
  expect(s.level).toBe("crit");
  expect(s.items[0]).toEqual({
    label: "Print deed",
    text: "blocked: drafts",
    level: "warn",
  });
  expect(s.items[1].level).toBe("crit");
  expect(s.items.at(-1)).toEqual({
    label: "gateway watch",
    text: "checked 20 s ago",
    level: "ok",
  });
});

test("no open requests and a fresh watch is ok; a late watch warns", () => {
  expect(
    parseGatewayRequests({
      requests: {
        available: true,
        open: [],
        watch: { checked_seconds_ago: 5 },
      },
    }).level,
  ).toBe("ok");
  expect(
    parseGatewayRequests({
      requests: {
        available: true,
        open: [],
        watch: { checked_seconds_ago: 900 },
      },
    }).level,
  ).toBe("warn");
});
