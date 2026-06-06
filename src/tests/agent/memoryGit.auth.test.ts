import { describe, expect, test } from "bun:test";

import {
  getGitRemoteUrl,
  normalizeCredentialBaseUrl,
} from "../../agent/memoryGit";
import { settingsManager } from "../../settings-manager";

describe("normalizeCredentialBaseUrl", () => {
  test("normalizes Letta Cloud URL to origin", () => {
    expect(normalizeCredentialBaseUrl("https://api.letta.com")).toBe(
      "https://api.letta.com",
    );
  });

  test("strips trailing slashes", () => {
    expect(normalizeCredentialBaseUrl("https://api.letta.com///")).toBe(
      "https://api.letta.com",
    );
  });

  test("drops path/query/fragment and keeps origin", () => {
    expect(
      normalizeCredentialBaseUrl(
        "https://api.letta.com/custom/path?foo=bar#fragment",
      ),
    ).toBe("https://api.letta.com");
  });

  test("preserves explicit port", () => {
    expect(normalizeCredentialBaseUrl("http://localhost:8283/v1/")).toBe(
      "http://localhost:8283",
    );
  });

  test("falls back to trimmed value when URL parsing fails", () => {
    expect(normalizeCredentialBaseUrl("not-a-valid-url///")).toBe(
      "not-a-valid-url",
    );
  });
});

describe("getGitRemoteUrl", () => {
  test("uses settings git base URL when env override is absent", () => {
    const previousBaseUrl = process.env.LETTA_BASE_URL;
    const previousGitBaseUrl = process.env.LETTA_GIT_BASE_URL;
    const originalGetSettings = settingsManager.getSettings;

    try {
      delete process.env.LETTA_GIT_BASE_URL;
      process.env.LETTA_BASE_URL = "http://example.test:8283/";
      settingsManager.getSettings = () =>
        ({
          env: { LETTA_GIT_BASE_URL: "http://100.80.49.10:18283/" },
        }) as unknown as ReturnType<typeof settingsManager.getSettings>;

      expect(getGitRemoteUrl("agent-123")).toBe(
        "http://100.80.49.10:18283/v1/git/agent-123/state.git",
      );
    } finally {
      settingsManager.getSettings = originalGetSettings;
      if (previousGitBaseUrl === undefined) {
        delete process.env.LETTA_GIT_BASE_URL;
      } else {
        process.env.LETTA_GIT_BASE_URL = previousGitBaseUrl;
      }
      if (previousBaseUrl === undefined) {
        delete process.env.LETTA_BASE_URL;
      } else {
        process.env.LETTA_BASE_URL = previousBaseUrl;
      }
    }
  });

  test("uses configured git base URL by default", () => {
    process.env.LETTA_GIT_BASE_URL = "http://100.80.49.10:18283/";
    expect(getGitRemoteUrl("agent-123")).toBe(
      "http://100.80.49.10:18283/v1/git/agent-123/state.git",
    );
    delete process.env.LETTA_GIT_BASE_URL;
  });

  test("falls back to main server URL when settings are not initialized", () => {
    const previousBaseUrl = process.env.LETTA_BASE_URL;
    process.env.LETTA_BASE_URL = "http://example.test:8283/";

    expect(getGitRemoteUrl("agent-123")).toBe(
      "http://example.test:8283/v1/git/agent-123/state.git",
    );

    if (previousBaseUrl === undefined) {
      delete process.env.LETTA_BASE_URL;
    } else {
      process.env.LETTA_BASE_URL = previousBaseUrl;
    }
  });

  test("expands self-hosted HTTP base URL override", () => {
    expect(getGitRemoteUrl("agent-123", "http://10.0.0.143:8283")).toBe(
      "http://10.0.0.143:8283/v1/git/agent-123/state.git",
    );
  });

  test("keeps full .git override URL unchanged", () => {
    expect(
      getGitRemoteUrl(
        "agent-123",
        "http://10.0.0.143:8283/custom/path/state.git",
      ),
    ).toBe("http://10.0.0.143:8283/custom/path/state.git");
  });

  test("keeps ssh override URL unchanged", () => {
    expect(
      getGitRemoteUrl(
        "agent-123",
        "ssh://adamsl@10.0.0.7/home/adamsl/memfs/memory.git",
      ),
    ).toBe("ssh://adamsl@10.0.0.7/home/adamsl/memfs/memory.git");
  });
});
