import { describe, expect, test } from "bun:test";
import { ReceptionistTranscriptController } from "../abstract/receptionist-transcript-controller.js";

describe("ReceptionistTranscriptController (State)", () => {
  test("keeps interim text visible after the committed transcript", () => {
    const seen = [];
    const controller = new ReceptionistTranscriptController({
      onChange: (snapshot) => seen.push(snapshot.text),
    });
    controller.accept("Hello Toyota", true);
    controller.accept("I need", false);
    expect(seen).toEqual(["Hello Toyota", "Hello Toyota I need"]);
    expect(controller.text).toBe("Hello Toyota I need");
  });

  test("merges final chunks once and replaces the interim suffix", () => {
    const controller = new ReceptionistTranscriptController();
    controller.accept("Toyota, check", true);
    controller.accept("Toyota, check the agenda", false);
    controller.accept("Toyota, check the agenda", true);
    expect(controller.committed).toBe("Toyota, check the agenda");
    expect(controller.text).toBe("Toyota, check the agenda");
  });

  test("does not erase the transcript when a caller sends separately", () => {
    const controller = new ReceptionistTranscriptController();
    controller.accept("Toyota, please help", true);
    expect(controller.text).toBe("Toyota, please help");
  });
});
