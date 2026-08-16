import { describe, expect, test } from "bun:test";
import {
  buildArchiveVerifyCommand,
  readArchivePathResponse,
} from "../abstract/archive-verify-command.js";

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

describe("readArchivePathResponse", () => {
  test("reads a successful response", () => {
    const result = readArchivePathResponse({
      ok: true,
      archive_path: "/archive/2026/august",
      archive_name: "receipt.jpg",
    });
    expect(result).toEqual({
      ok: true,
      archivePath: "/archive/2026/august",
      archiveName: "receipt.jpg",
      error: null,
    });
  });

  test("defaults archiveName to empty string when the server omits it", () => {
    const result = readArchivePathResponse({
      ok: true,
      archive_path: "/archive",
    });
    expect(result.archiveName).toBe("");
  });

  test("surfaces the server's error message on ok:false", () => {
    const result = readArchivePathResponse({
      ok: false,
      error: "No intake found",
    });
    expect(result.ok).toBe(false);
    expect(result.archivePath).toBeNull();
    expect(result.error).toBe("No intake found");
  });

  test("falls back to a generic error when ok:false carries no message", () => {
    const result = readArchivePathResponse({ ok: false });
    expect(result.error).toBe("archive path not found");
  });

  test("treats ok:true with a missing archive_path as failure", () => {
    const result = readArchivePathResponse({ ok: true });
    expect(result.ok).toBe(false);
  });

  test("fails closed on a malformed (non-object) response", () => {
    expect(readArchivePathResponse(null).ok).toBe(false);
    expect(readArchivePathResponse(undefined).ok).toBe(false);
    expect(readArchivePathResponse("oops").ok).toBe(false);
    expect(readArchivePathResponse(42).ok).toBe(false);
  });
});
