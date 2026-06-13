import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";

const retrieveMock = mock(async (_agentId: string) => ({
  tags: [] as string[],
}));
const updateMock = mock(
  async (_agentId: string, _body: { tags: string[] }) => ({}),
);

mock.module("../../agent/client", () => ({
  getClient: mock(async () => ({
    agents: {
      retrieve: retrieveMock,
      update: updateMock,
    },
  })),
  getServerUrl: () => "https://example.test",
}));

const { addGitMemoryTag, GIT_MEMORY_ENABLED_TAG } = await import(
  "../../agent/memoryGit"
);

describe("addGitMemoryTag", () => {
  beforeEach(() => {
    retrieveMock.mockReset();
    updateMock.mockReset();
  });

  afterEach(() => {
    retrieveMock.mockImplementation(async (_agentId: string) => ({
      tags: [] as string[],
    }));
    updateMock.mockImplementation(
      async (_agentId: string, _body: { tags: string[] }) => ({}),
    );
  });

  test("re-checks live agent tags before updating when prefetched tags omit the memfs tag", async () => {
    retrieveMock.mockImplementation(async () => ({
      tags: ["origin:letta-code", GIT_MEMORY_ENABLED_TAG],
    }));

    await addGitMemoryTag("agent-123", { tags: ["origin:letta-code"] });

    expect(retrieveMock).toHaveBeenCalledTimes(1);
    expect(updateMock).not.toHaveBeenCalled();
  });

  test("deduplicates outgoing tags when update is needed", async () => {
    retrieveMock.mockImplementation(async () => ({
      tags: ["origin:letta-code", "origin:letta-code"],
    }));

    await addGitMemoryTag("agent-123", { tags: ["origin:letta-code"] });

    expect(updateMock).toHaveBeenCalledTimes(1);
    expect(updateMock.mock.calls[0]?.[1]).toEqual({
      tags: ["origin:letta-code", GIT_MEMORY_ENABLED_TAG],
    });
  });

  test("uses prefetched tags directly when they already include the memfs tag", async () => {
    await addGitMemoryTag("agent-123", {
      tags: ["origin:letta-code", GIT_MEMORY_ENABLED_TAG],
    });

    expect(retrieveMock).not.toHaveBeenCalled();
    expect(updateMock).not.toHaveBeenCalled();
  });
});
