import { describe, expect, test } from "bun:test";
import {
  ClaudeSdkTokenRateController,
  currentRunText,
  formatTokens,
  historyNote,
  primaryWindow,
  RATE_BAR_FULL_SCALE,
} from "../implementation/claude-sdk-token-rate-controller.js";
import { FakeDocument } from "./_fake-dom.js";

const IDS = [
  "claude-sdk-rate-primary",
  "claude-sdk-rate-current",
  "claude-sdk-rate-fill",
  "claude-sdk-rate-windows",
  "claude-sdk-rate-note",
];

function setup(payload) {
  const doc = new FakeDocument();
  for (const id of IDS) doc.createElement("div").id = id;
  const controller = new ClaudeSdkTokenRateController({
    doc,
    http: {
      getJSON: async () => {
        if (payload instanceof Error) throw payload;
        return payload;
      },
    },
    setInterval: () => 1,
    clearInterval: () => {},
  });
  return { doc, controller };
}

function window_(
  seconds,
  label,
  tokensPerMinute,
  total,
  runs,
  complete = true,
) {
  return {
    seconds,
    label,
    runs,
    input_tokens: 0,
    output_tokens: 0,
    cache_tokens: 0,
    total_tokens: total,
    tokens_per_minute: tokensPerMinute,
    complete,
  };
}

describe("formatTokens", () => {
  test("scales to k and M so a rate fits the Windows-98 strip", () => {
    expect(formatTokens(850)).toBe("850");
    expect(formatTokens(8400)).toBe("8.4k");
    expect(formatTokens(1_240_000)).toBe("1.2M");
    expect(formatTokens(undefined)).toBe("0");
  });
});

describe("primaryWindow", () => {
  test("headlines the 5-minute window, not the spiky 1-minute one", () => {
    const windows = [
      window_(60, "last minute", 9, 9, 1),
      window_(300, "last 5 min", 3, 15, 1),
    ];
    expect(primaryWindow(windows).seconds).toBe(300);
  });

  test("falls back to whatever the server sent", () => {
    expect(primaryWindow([window_(60, "last minute", 1, 1, 1)]).seconds).toBe(
      60,
    );
    expect(primaryWindow(null)).toBe(null);
  });
});

describe("currentRunText", () => {
  test("says 'so far' only while the run is live", () => {
    expect(
      currentRunText({ status: "running", model: "haiku", total_tokens: 2000 }),
    ).toContain("so far");
    expect(
      currentRunText({
        status: "complete",
        model: "haiku",
        total_tokens: 2000,
      }),
    ).toBe("last run (haiku): 2.0k tokens");
    expect(currentRunText(null)).toBe("");
  });
});

describe("historyNote", () => {
  test("says plainly that there is nothing to average yet", () => {
    expect(historyNote({ sample_count: 0 })).toContain("No finished SDK runs");
  });
});

describe("ClaudeSdkTokenRateController", () => {
  test("renders the headline rate, the meter and one cell per window", async () => {
    const { doc, controller } = setup({
      ok: true,
      sample_count: 3,
      observed_since: 1_700_000_000,
      current_run: {
        run_id: "r",
        status: "running",
        model: "haiku",
        total_tokens: 4000,
      },
      windows: [
        window_(60, "last minute", 0, 0, 0),
        window_(300, "last 5 min", 50000, 250000, 5),
        window_(3600, "last hour", 12000, 720000, 20, false),
      ],
    });

    await controller.poll();

    expect(doc.getElementById("claude-sdk-rate-primary").textContent).toBe(
      "50.0k tok/min",
    );
    expect(doc.getElementById("claude-sdk-rate-current").textContent).toContain(
      "so far",
    );
    const fill = doc.getElementById("claude-sdk-rate-fill");
    expect(fill.style.width).toBe(
      `${((50000 / RATE_BAR_FULL_SCALE) * 100).toFixed(1)}%`,
    );
    expect(fill.classList.contains("is-hot")).toBe(false);
    const cells = doc.getElementById("claude-sdk-rate-windows").children;
    expect(cells.length).toBe(3);
    expect(cells[2].classList.contains("is-partial")).toBe(true);
  });

  test("the meter reads hot past 60% of full scale and never overflows", async () => {
    const { doc, controller } = setup({
      ok: true,
      sample_count: 1,
      windows: [window_(300, "last 5 min", RATE_BAR_FULL_SCALE * 4, 1, 1)],
    });

    await controller.poll();

    const fill = doc.getElementById("claude-sdk-rate-fill");
    expect(fill.style.width).toBe("100.0%");
    expect(fill.classList.contains("is-hot")).toBe(true);
  });

  test("an idle history says so instead of showing a stale rate", async () => {
    const { doc, controller } = setup({
      ok: true,
      sample_count: 0,
      windows: [window_(300, "last 5 min", 0, 0, 0)],
    });

    await controller.poll();

    expect(doc.getElementById("claude-sdk-rate-primary").textContent).toBe(
      "0 tok/min",
    );
    expect(
      doc
        .getElementById("claude-sdk-rate-primary")
        .classList.contains("is-idle"),
    ).toBe(true);
    expect(doc.getElementById("claude-sdk-rate-note").textContent).toContain(
      "No finished SDK runs",
    );
  });

  test("a failed fetch is reported, not silently frozen", async () => {
    const { doc, controller } = setup(new Error("network down"));

    await controller.poll();

    expect(doc.getElementById("claude-sdk-rate-primary").textContent).toBe(
      "unavailable",
    );
    expect(doc.getElementById("claude-sdk-rate-note").textContent).toContain(
      "network down",
    );
  });
});
