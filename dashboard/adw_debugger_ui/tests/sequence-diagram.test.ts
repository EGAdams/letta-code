import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { DiagramColumn, DiagramModel } from "../src/contracts";
import SequenceDiagram from "../src/ui/SequenceDiagram.vue";

const TORTURE =
  "line one; \"double\" and 'single'\nend\n<script>window.pwned = 1</script> %%{init: {}}%% -->> Note over A: end;\n" +
  "long ".repeat(80);

function column(
  instanceId: string,
  status: DiagramColumn["status"],
  selected = false,
): DiagramColumn {
  return {
    instanceId,
    name: "lookup",
    attempt: 1,
    status,
    statusLabel: status.toUpperCase(),
    detail: "3s",
    purpose: "p",
    selected,
  };
}

const model: DiagramModel = {
  runId: "r1",
  columns: [
    column("r1:lookup-1", "pass"),
    column("r1:lookup-2", "stalled", true),
    column("r1:report", "waiting"),
  ],
  rows: [
    {
      id: "e1",
      from: 1,
      to: 1,
      text: TORTURE,
      dashed: false,
      kind: "tool_call",
    },
    {
      id: "e2",
      from: 1,
      to: 1,
      text: "returned",
      dashed: true,
      kind: "tool_result",
    },
    {
      id: "e3",
      from: 0,
      to: 2,
      text: "forward",
      dashed: false,
      kind: "message",
    },
    { id: "e4", from: 2, to: 0, text: "back", dashed: false, kind: "message" },
  ],
};

describe("SequenceDiagram", () => {
  const wrapper = mount(SequenceDiagram, { props: { model } });

  it("draws an upper and a lower box for every phase, both carrying the same status", () => {
    for (const col of model.columns) {
      const boxes = wrapper.findAll(`[data-instance="${col.instanceId}"]`);
      expect(boxes.map((box) => box.attributes("data-edge"))).toEqual([
        "top",
        "bottom",
      ]);
      expect(boxes.map((box) => box.attributes("data-status"))).toEqual([
        col.status,
        col.status,
      ]);
    }
  });

  it("tells two phases with the same name apart by instance id", () => {
    expect(
      wrapper
        .findAll(".sd-titles-top .sd-box")
        .map((box) => box.attributes("data-instance")),
    ).toEqual(["r1:lookup-1", "r1:lookup-2", "r1:report"]);
  });

  it("marks only the selected instance, on both of its boxes", () => {
    expect(
      wrapper
        .findAll(".sd-selected")
        .map((box) => box.attributes("data-instance")),
    ).toEqual(["r1:lookup-2", "r1:lookup-2"]);
  });

  it("emits the exact instance from either box", async () => {
    const [top, bottom] = wrapper.findAll('[data-instance="r1:lookup-2"]');
    await top.trigger("click");
    await bottom.trigger("click");
    expect(wrapper.emitted("phase-click")).toEqual([
      ["r1:lookup-2"],
      ["r1:lookup-2"],
    ]);
  });

  it("shows the whole recorded text as text, never as markup", () => {
    const label = wrapper.find('[data-kind="tool_call"] .sd-label');
    expect(label.text()).toBe(TORTURE.trim());
    expect(label.element.textContent).toBe(TORTURE);
    expect(wrapper.find("script").exists()).toBe(false);
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined();
  });

  it("distinguishes self-calls, returns and the two directions", () => {
    const classes = wrapper.findAll(".sd-message").map((message) =>
      message
        .classes()
        .filter((name) => name !== "sd-message")
        .sort()
        .join(" "),
    );
    expect(classes).toEqual([
      "sd-self",
      "sd-dashed sd-self",
      "sd-right",
      "sd-left",
    ]);
  });

  it("keeps zoom across a model update", async () => {
    await wrapper.find('[aria-label="Zoom in"]').trigger("click");
    await wrapper.setProps({
      model: { ...model, rows: model.rows.slice(0, 1) },
    });
    expect(wrapper.find(".sd-zoom-value").text()).toBe("110%");
    expect(wrapper.findAll(".sd-message")).toHaveLength(1);
  });
});
