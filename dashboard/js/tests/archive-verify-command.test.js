import { describe, expect, test } from "bun:test";
import { buildArchiveVerifyCommand } from "../abstract/archive-verify-command.js";

describe("buildArchiveVerifyCommand", () => {
  test("cds into the archive directory and lists one entry per line", () => {
    const cmd = buildArchiveVerifyCommand(
      "/archive/2026/august",
      "receipt.jpg",
    );
    expect(cmd).toContain("cd '/archive/2026/august'");
    expect(cmd).toContain("ls -a1");
  });

  test("highlights the exact named file via awk, not a glob", () => {
    const cmd = buildArchiveVerifyCommand("/archive", "receipt.jpg");
    expect(cmd).toContain("target='receipt.jpg'");
    expect(cmd).toContain("if ($0 == target)");
  });

  test("shell-quotes a path containing a single quote", () => {
    const cmd = buildArchiveVerifyCommand("/archive/o'brien", "r.jpg");
    expect(cmd).toContain(`'/archive/o'"'"'brien'`);
  });
});
