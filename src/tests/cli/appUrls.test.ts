import { afterEach, describe, expect, test } from "bun:test";
import { buildChatUrl, getAppBaseUrl } from "../../cli/helpers/appUrls";

const originalBaseUrl = process.env.LETTA_BASE_URL;

afterEach(() => {
  if (originalBaseUrl === undefined) {
    delete process.env.LETTA_BASE_URL;
  } else {
    process.env.LETTA_BASE_URL = originalBaseUrl;
  }
});

describe("app URL helpers", () => {
  test("cloud API URLs map to the hosted app", () => {
    expect(getAppBaseUrl("https://api.letta.com")).toBe(
      "https://app.letta.com",
    );
    expect(getAppBaseUrl("https://api.letta.com/v1")).toBe(
      "https://app.letta.com",
    );
  });

  test("self-hosted URLs stay on the configured server", () => {
    process.env.LETTA_BASE_URL = "http://100.80.49.10:8283";

    expect(buildChatUrl("agent-local")).toBe(
      "http://100.80.49.10:8283/chat/agent-local",
    );
  });

  test("chat URLs preserve conversation query params", () => {
    process.env.LETTA_BASE_URL = "http://localhost:8283/v1";

    expect(
      buildChatUrl("agent-local", {
        conversationId: "conv-123",
        view: "memory",
      }),
    ).toBe("http://localhost:8283/chat/agent-local?view=memory&conversation=conv-123");
  });
});
