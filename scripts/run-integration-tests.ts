#!/usr/bin/env bun
/**
 * Runs integration tests serially, stopping on the first file failure.
 *
 * Sentinel handling: the bail sentinel (/tmp/letta-integration-bail) is cleared
 * BEFORE each file so stale sentinels don't block a fresh run. It is also checked
 * AFTER each file to catch a race condition where a fire-and-forget logger.log()
 * call writes the sentinel during Bun's cleanup phase after tests pass (exit 0),
 * meaning the sentinel exists even though the subprocess exited successfully.
 */
import { existsSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const BAIL_SENTINEL_PATH = "/tmp/letta-integration-bail";
const TEST_DIR = join(import.meta.dir, "../src/integration-tests");

const files = readdirSync(TEST_DIR)
  .filter((f) => f.endsWith(".test.ts"))
  .sort()
  .map((f) => join(TEST_DIR, f));

const shortName = (f: string) => f.replace(`${TEST_DIR}/`, "");

let failed = false;
for (const file of files) {
  // Clear sentinel before each file — handles stale sentinels from prior runs
  // and the post-exit race condition from the previous file.
  try {
    rmSync(BAIL_SENTINEL_PATH, { force: true });
  } catch {}

  console.log(`\n▶ ${shortName(file)}`);
  const proc = Bun.spawnSync(["bun", "test", file], {
    env: process.env,
    stdio: ["inherit", "inherit", "inherit"],
  });

  // Check sentinel AFTER the run: catches the race where a fire-and-forget
  // logger.log() writes the sentinel during cleanup of a passing test
  // (process exits 0 but a bail-triggering log message completed async).
  const sentinelAfter = existsSync(BAIL_SENTINEL_PATH);

  if (proc.exitCode !== 0 || sentinelAfter) {
    console.error(
      `\n✗ Failed: ${shortName(file)}${sentinelAfter ? " (bail sentinel)" : ""}`,
    );
    failed = true;
    break;
  }
}

process.exit(failed ? 1 : 0);
