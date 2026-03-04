import { describe, expect, test } from "bun:test";

import {
  getGitRemoteUrl,
  normalizeCredentialBaseUrl,
} from "../../agent/memoryGit";

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
