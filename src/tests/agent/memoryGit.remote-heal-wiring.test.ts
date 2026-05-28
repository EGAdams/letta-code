import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

test("pullMemory always reconciles origin to current target URL", () => {
  const source = readFileSync(
    join(process.cwd(), "src/agent/memoryGit.ts"),
    "utf-8",
  );
  const pullMemoryStart = source.indexOf("export async function pullMemory(");
  expect(pullMemoryStart).toBeGreaterThan(-1);
  const pullMemoryBody = source.slice(pullMemoryStart);

  expect(pullMemoryBody).toContain("await ensureRemote(dir, url);");
  expect(pullMemoryBody).not.toContain(
    "if (remoteOverride) {\n    await ensureRemote(dir, url);",
  );
});
