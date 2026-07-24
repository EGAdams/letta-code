import { describe, expect, test } from "bun:test";
import { PollingController } from "../abstract/polling-controller.interface.js";
import { StatementReviewDialog } from "../implementation/statement-review-dialog.js";

const source = async (relativePath) =>
  Bun.file(new URL(relativePath, import.meta.url)).text();

describe("statement-review dependency boundaries", () => {
  test("decision and action interfaces never import implementations", async () => {
    const decisionSource = await source(
      "../abstract/statement-review.interface.js",
    );
    const actionsSource = await source(
      "../abstract/statement-review-actions.interface.js",
    );

    const implementationImport =
      /(?:import|export)[\s\S]*?\bfrom\s+["'][^"']*implementation\//;
    expect(decisionSource).not.toMatch(implementationImport);
    expect(actionsSource).not.toMatch(implementationImport);
  });

  test("the dialog depends on abstract ports, not dashboard implementations", async () => {
    const dialogSource = await source(
      "../implementation/statement-review-dialog.js",
    );

    expect(dialogSource).toContain("StatementReviewActions");
    expect(dialogSource).toContain("PollingController");
    expect(dialogSource).not.toContain("dashboard-boot");
    expect(dialogSource).not.toContain("InputOptionsRenderer");
    expect(dialogSource).not.toContain("globalThis.open");
    expect(dialogSource).not.toMatch(/\bAM\./);
  });

  test("the concrete dialog uses the shared polling Template Method", () => {
    expect(StatementReviewDialog.prototype).toBeInstanceOf(PollingController);
    expect(Object.hasOwn(StatementReviewDialog.prototype, "start")).toBe(false);
    expect(Object.hasOwn(StatementReviewDialog.prototype, "stop")).toBe(false);
  });
});
