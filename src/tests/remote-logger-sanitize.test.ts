import { describe, expect, test } from "bun:test";
import { RemoteLogger } from "../logger/RemoteLogger";

describe("RemoteLogger sanitizeLogMessage", () => {
  test("preserves traceback newlines in transported object_data", async () => {
    const requests: Array<{ url: string; body: string }> = [];

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requests.push({ url, body: String(init?.body ?? "") });
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    try {
      const logger = new RemoteLogger("RemoteLogger_SanitizeTraceback_2026");
      await logger.log(
        [
          "Traceback (most recent call last):",
          '  File "/tmp/demo.py", line 4, in <module>',
          "    raise ValueError('bad input')",
          'ValueError: bad "input"',
        ].join("\n"),
      );

      const update = requests.find((req) => req.url.includes("/object/update"));
      expect(update).toBeDefined();
      const payload = JSON.parse(update?.body ?? "{}") as {
        object_data?: string;
      };
      const state = JSON.parse(payload.object_data ?? "{}") as {
        logObjects?: Array<{ message?: string }>;
      };
      const lastMessage = state.logObjects?.at(-1)?.message ?? "";

      expect(lastMessage).toContain("Traceback (most recent call last):\n");
      expect(lastMessage).toContain(
        "File ”/tmp/demo.py”, line 4, in <module>\n",
      );
      expect(lastMessage).toContain("ValueError: bad ”input”");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
