import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("system prompt warning wiring", () => {
  test("defines helper for recommending the default coding prompt", () => {
    const appPath = fileURLToPath(
      new URL("../../cli/App.tsx", import.meta.url),
    );
    const source = readFileSync(appPath, "utf-8");

    expect(source).toContain(
      "const buildDefaultPromptRecommendationLines = useCallback(",
    );
    expect(source).toContain(
      '"⚠ **Prompt:** This agent is using a custom or legacy system prompt."',
    );
    expect(source).toContain(
      '"If you want standard Letta Code coding behavior, run **/system default**."',
    );
  });

  test("shows the recommendation in startup status, agent switch, and /clear flows", () => {
    const appPath = fileURLToPath(
      new URL("../../cli/App.tsx", import.meta.url),
    );
    const source = readFileSync(appPath, "utf-8");

    const startupAnchor = "const startupSystemPromptWarning =";
    const startupIndex = source.indexOf(startupAnchor);
    expect(startupIndex).toBeGreaterThanOrEqual(0);
    expect(source.slice(startupIndex, startupIndex + 1200)).toContain(
      "buildDefaultPromptRecommendationLines(agentState)",
    );

    const switchAnchor = "const successOutput = isSpecificConv";
    const switchIndex = source.indexOf(switchAnchor);
    expect(switchIndex).toBeGreaterThanOrEqual(0);
    expect(source.slice(switchIndex, switchIndex + 1800)).toContain(
      "buildDefaultPromptRecommendationLines(agent)",
    );

    const clearAnchor = 'if (msg.trim() === "/clear")';
    const clearIndex = source.indexOf(clearAnchor);
    expect(clearIndex).toBeGreaterThanOrEqual(0);
    expect(source.slice(clearIndex, clearIndex + 3200)).toContain(
      "buildDefaultPromptRecommendationLines(agentState)",
    );
  });
});
