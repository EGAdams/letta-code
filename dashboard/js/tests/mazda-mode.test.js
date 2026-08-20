/**
 * The Automatic / Semi-Automatic switch.
 *
 * The failure worth guarding: a switch showing a mode the server is not
 * actually in. An operator who reads "Mazda Automatic" on a box where dispatch
 * is still blocked will feed a stack of documents through the scanner and wait
 * for filing that is never going to happen -- and the reverse leaves paid
 * reading switched on by someone who believes they turned it off. So the
 * position of this control is only ever changed by an answer from the server,
 * and any failure puts it back where it was.
 */
import { describe, expect, test } from "bun:test";
import {
  buildMazdaModePayload,
  MAZDA_MODE,
  MAZDA_MODE_LABELS,
  mazdaModeLabel,
  readMazdaModeDataset,
  readMazdaModeResponse,
  summarizeMazdaMode,
} from "../abstract/mazda-mode.interface.js";
import { ManualEntryForm } from "../implementation/manual-entry-form.js";
import { FakeDocument } from "./_fake-dom.js";

function fakeHttp(responses) {
  const calls = [];
  return {
    calls,
    async getJSON(url) {
      calls.push(["GET", url]);
      return responses[url] ?? { ok: true };
    },
    async postJSON(url, body, opts) {
      calls.push(["POST", url, body, opts]);
      const entry = responses[url];
      if (typeof entry === "function") return entry(body);
      return entry ?? { ok: true };
    },
  };
}

function setup(responses = {}, dataset = {}) {
  const doc = new FakeDocument();
  doc.location = { reload: () => {} };
  const root = doc.createElement("div");
  root.id = "manual-entry-root";
  root.dataset.imagePath = "/staged/scan.jpg";
  root.dataset.conversationId = "conv-1";
  root.dataset.scannerKey = "freezer";
  Object.assign(root.dataset, dataset);
  doc.add(root);
  const http = fakeHttp({
    "/api/vendor-keys": { ok: true, vendor_keys: [] },
    "/api/rol-finance-categories": { ok: true, categories: ["Utilities"] },
    "/api/manual-receipt-entry-archive-preview": { ok: false, error: "n/a" },
    ...responses,
  });
  const form = new ManualEntryForm({
    http,
    root,
    doc,
    mountTerminal: async () => null,
  });
  return { form, http };
}

function posts(http, url) {
  return http.calls.filter((c) => c[0] === "POST" && c[1] === url);
}

describe("the two positions", () => {
  test("wire values stay the intake pipeline's own words", () => {
    // Every stored intake record, status message and Python test already says
    // these. Renaming them would rewrite intake history to mean the same thing
    // differently.
    expect(MAZDA_MODE.AUTOMATIC).toBe("auto");
    expect(MAZDA_MODE.SEMI_AUTOMATIC).toBe("human_only");
  });

  test("the label names the state, not the action", () => {
    expect(mazdaModeLabel(true)).toBe("Mazda Automatic");
    expect(mazdaModeLabel(false)).toBe("Mazda Semi-Automatic");
    expect(Object.values(MAZDA_MODE_LABELS).sort()).toEqual([
      "Mazda Automatic",
      "Mazda Semi-Automatic",
    ]);
  });
});

describe("readMazdaModeDataset", () => {
  test("reads the position Python stamped into the mount point", () => {
    expect(
      readMazdaModeDataset({
        mazdaAutomatic: "false",
        mazdaModeLabel: "Mazda Semi-Automatic",
      }),
    ).toMatchObject({
      automatic: false,
      mode: "human_only",
      label: "Mazda Semi-Automatic",
    });
  });

  test("an unstamped page reads as Automatic", () => {
    // MAZDA_DECISION_MODE unset means 'auto', so claiming Semi-Automatic would
    // be telling the operator Mazda is switched off on a box where she is not.
    expect(readMazdaModeDataset({}).automatic).toBe(true);
    expect(readMazdaModeDataset(undefined).label).toBe("Mazda Automatic");
  });
});

describe("buildMazdaModePayload", () => {
  test("sends a boolean, never a mode name", () => {
    expect(buildMazdaModePayload(true)).toEqual({ automatic: true });
    expect(buildMazdaModePayload(false)).toEqual({ automatic: false });
    expect(buildMazdaModePayload("yes")).toEqual({ automatic: false });
  });
});

describe("readMazdaModeResponse", () => {
  test("accepts a well-formed answer", () => {
    expect(
      readMazdaModeResponse({
        ok: true,
        mode: "human_only",
        automatic: false,
        label: "Mazda Semi-Automatic",
        source: "operator",
      }),
    ).toEqual({
      ok: true,
      mode: "human_only",
      automatic: false,
      label: "Mazda Semi-Automatic",
      source: "operator",
      error: null,
    });
  });

  test("an unknown mode is not ok, however cheerful the payload", () => {
    const state = readMazdaModeResponse({
      ok: true,
      mode: "semi",
      automatic: true,
      label: "Mazda Automatic",
    });
    expect(state.ok).toBe(false);
    expect(state.mode).toBe("");
  });

  test("a rejected request keeps its reason", () => {
    const state = readMazdaModeResponse({
      ok: false,
      mode: "auto",
      automatic: true,
      label: "Mazda Automatic",
      source: "default",
      error: "request body must be an object",
    });
    expect(state.ok).toBe(false);
    expect(state.error).toBe("request body must be an object");
  });

  test("garbage is not ok", () => {
    expect(readMazdaModeResponse(null).ok).toBe(false);
    expect(readMazdaModeResponse("auto").ok).toBe(false);
  });
});

describe("summarizeMazdaMode", () => {
  test("says out loud that the document on screen is unaffected", () => {
    const sentence = summarizeMazdaMode({
      ok: true,
      automatic: true,
      label: "Mazda Automatic",
    });
    expect(sentence).toContain("next scanned document");
    expect(sentence).toContain("unchanged");
  });

  test("semi-automatic names the button that does the reading", () => {
    expect(
      summarizeMazdaMode({
        ok: true,
        automatic: false,
        label: "Mazda Semi-Automatic",
      }),
    ).toContain("Mazda Fill");
  });

  test("a failure says the switch was put back", () => {
    expect(summarizeMazdaMode({ ok: false, error: "boom" })).toContain(
      "put back",
    );
  });
});

describe("the switch on the form", () => {
  test("mounts beside the model dropdown, showing the stamped mode", async () => {
    const { form } = setup(
      {},
      {
        mazdaAutomatic: "false",
        mazdaModeLabel: "Mazda Semi-Automatic",
      },
    );
    await form.mount();
    expect(form.mazdaModeCheckbox.checked).toBe(false);
    expect(form.mazdaModeLabelEl.textContent).toBe("Mazda Semi-Automatic");
    // Same row as Mazda Fill and its model dropdown: the switch answers the
    // question those two raise -- "do I have to press this at all?"
    const row = form.mazdaModelSelect.parent;
    expect(row.children).toContain(form.mazdaModeCheckbox.parent);
  });

  test("turning it on posts the boolean and adopts the server's label", async () => {
    const { form, http } = setup(
      {
        "/api/mazda-mode": {
          ok: true,
          mode: "auto",
          automatic: true,
          label: "Mazda Automatic",
          source: "operator",
        },
      },
      { mazdaAutomatic: "false", mazdaModeLabel: "Mazda Semi-Automatic" },
    );
    await form.mount();
    await form._setMazdaMode(true);
    expect(posts(http, "/api/mazda-mode")[0][2]).toEqual({ automatic: true });
    expect(form.mazdaModeCheckbox.checked).toBe(true);
    expect(form.mazdaModeLabelEl.textContent).toBe("Mazda Automatic");
  });

  test("a refused change puts the switch back where it was", async () => {
    const { form } = setup(
      { "/api/mazda-mode": { ok: false, error: "no" } },
      { mazdaAutomatic: "false", mazdaModeLabel: "Mazda Semi-Automatic" },
    );
    await form.mount();
    form.mazdaModeCheckbox.checked = true;
    await form._setMazdaMode(true);
    expect(form.mazdaModeCheckbox.checked).toBe(false);
    expect(form.mazdaModeLabelEl.textContent).toBe("Mazda Semi-Automatic");
  });

  test("a dead connection puts the switch back too", async () => {
    const { form } = setup(
      {
        "/api/mazda-mode": () => {
          throw new Error("network down");
        },
      },
      { mazdaAutomatic: "true", mazdaModeLabel: "Mazda Automatic" },
    );
    await form.mount();
    form.mazdaModeCheckbox.checked = false;
    await form._setMazdaMode(false);
    expect(form.mazdaModeCheckbox.checked).toBe(true);
    expect(form.mazdaModeLabelEl.textContent).toBe("Mazda Automatic");
  });

  test("changing the mode never reads or stores the document on screen", async () => {
    const { form, http } = setup({
      "/api/mazda-mode": {
        ok: true,
        mode: "auto",
        automatic: true,
        label: "Mazda Automatic",
        source: "operator",
      },
    });
    await form.mount();
    await form._setMazdaMode(true);
    expect(posts(http, "/api/mazda-fill")).toHaveLength(0);
    expect(posts(http, "/api/manual-receipt-entry")).toHaveLength(0);
    expect(posts(http, "/api/manual-statement-entry")).toHaveLength(0);
  });
});
