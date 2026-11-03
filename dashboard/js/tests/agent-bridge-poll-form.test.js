import { describe, expect, test } from "bun:test";
import {
  readForm,
  renderEditForm,
  withTyped,
} from "../abstract/agent-bridge-poll-form.js";
import { renderPollPage } from "../abstract/agent-bridge-poll-render.js";

const row = (key, value, inFile = true) => ({
  key,
  label: `L ${key}`,
  help: "h",
  unit: "s",
  value,
  in_file: inFile,
});
const payload = {
  polling: "active",
  reason: "polling",
  service: {},
  state: null,
  settings_path: "/x/poll_settings.json",
  restart_command: "systemctl --user restart agent-bridge-worker.service",
  settings: [
    row("idle_seconds", 30),
    row("burst_seconds", 5),
    row("burst_window_seconds", 300),
    row("slow_down_seconds", 3600),
    row("error_base_seconds", 30),
    row("error_max_seconds", 900),
    row("active_hours", null),
  ],
};
const typed = {
  idle_seconds: "45",
  burst_seconds: "5",
  burst_window_seconds: "300",
  slow_down_seconds: "3600",
  error_base_seconds: "30",
  error_max_seconds: "900",
  around_clock: false,
  start_hour: "7",
  end_hour: "24",
};

describe("edit form", () => {
  test("has an input for every setting and the save button", () => {
    const html = renderEditForm(payload);
    for (const r of payload.settings.filter((r) => r.key !== "active_hours"))
      expect(html).toContain(`name="${r.key}" value="${r.value}"`);
    expect(html).toContain('name="around_clock" checked');
    expect(html).toContain('name="start_hour" disabled');
    expect(html).toContain("Save and restart worker");
  });

  test("set active hours are selected and enabled", () => {
    const d = {
      ...payload,
      settings: [row("active_hours", { start_hour: 8, end_hour: 22 })],
    };
    const html = renderEditForm(d);
    expect(html).toContain('<option value="8" selected>08:00</option>');
    expect(html).toContain('<option value="22" selected>22:00</option>');
    expect(html).not.toContain("disabled");
  });

  test("shows the worker's problems beside their field, escaped", () => {
    const html = renderEditForm(payload, {
      editing: true,
      ok: false,
      message: "Those settings were not saved.",
      problems: [
        { field: "idle_seconds", message: "Input should be >= 10 <b>" },
      ],
    });
    expect(html).toContain("abp-err");
    expect(html).toContain("Input should be &gt;= 10 &lt;b&gt;");
  });

  test("saving disables the buttons", () => {
    const html = renderEditForm(payload, { editing: true, saving: true });
    expect(html).toContain("Saving and restarting…");
    expect(html.match(/disabled/g).length).toBeGreaterThanOrEqual(2);
  });
});

describe("readForm", () => {
  test("numbers and hours become the save payload", () => {
    expect(readForm(typed).payload).toEqual({
      idle_seconds: 45,
      burst_seconds: 5,
      burst_window_seconds: 300,
      slow_down_seconds: 3600,
      error_base_seconds: 30,
      error_max_seconds: 900,
      active_hours: { start_hour: 7, end_hour: 24 },
    });
  });

  test("around the clock sends null", () => {
    expect(
      readForm({ ...typed, around_clock: true }).payload.active_hours,
    ).toBeNull();
  });

  test("blank or words are refused before anything is sent", () => {
    const r = readForm({ ...typed, idle_seconds: "", burst_seconds: "soon" });
    expect(r.payload).toBeUndefined();
    expect(r.problems.map((p) => p.field)).toEqual([
      "idle_seconds",
      "burst_seconds",
    ]);
  });

  test("a refused form keeps what was typed", () => {
    expect(renderEditForm(withTyped(payload, typed))).toContain(
      'name="idle_seconds" value="45"',
    );
  });
});

describe("page", () => {
  test("shows the table with an Edit button, or the form while editing", () => {
    expect(renderPollPage(payload, { mode: "unknown", fraction: 0 })).toContain(
      'data-abp="edit"',
    );
    const editing = renderPollPage(
      payload,
      { mode: "unknown", fraction: 0 },
      { editing: true },
    );
    expect(editing).toContain('data-abp="form"');
    expect(editing).not.toContain('data-abp="edit"');
  });

  test("a saved message shows above the table", () => {
    const html = renderPollPage(
      payload,
      { mode: "unknown", fraction: 0 },
      { ok: true, message: "Saved." },
    );
    expect(html).toContain('abp-msg abp-ok">Saved.');
  });
});
