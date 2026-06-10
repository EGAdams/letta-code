import { describe, expect, test } from "bun:test";
import { ActivePoller } from "../implementation/active-poller.js";

class FakeController {
  constructor() {
    this.started = 0;
    this.stopped = 0;
  }
  async start() {
    this.started++;
  }
  stop() {
    this.stopped++;
  }
}

describe("ActivePoller", () => {
  test("run stops the previous controller before starting the new one", async () => {
    const p = new ActivePoller();
    const a = new FakeController();
    const b = new FakeController();

    await p.run(a);
    expect(a.started).toBe(1);
    expect(p.current).toBe(a);

    await p.run(b);
    expect(a.stopped).toBe(1); // previous halted
    expect(b.started).toBe(1);
    expect(p.current).toBe(b);
  });

  test("stop halts and forgets the current controller", async () => {
    const p = new ActivePoller();
    const a = new FakeController();
    await p.run(a);
    p.stop();
    expect(a.stopped).toBe(1);
    expect(p.current).toBeNull();
    p.stop(); // safe when idle
    expect(a.stopped).toBe(1);
  });

  test("re-running the same controller does not stop it", async () => {
    const p = new ActivePoller();
    const a = new FakeController();
    await p.run(a);
    await p.run(a);
    expect(a.stopped).toBe(0);
    expect(a.started).toBe(2);
  });
});
