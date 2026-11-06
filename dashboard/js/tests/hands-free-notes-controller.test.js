import { describe, expect, test } from "bun:test";
import { HandsFreeNotesController } from "../implementation/hands-free-notes-controller.js";
import { FakeDocument, FakeElement } from "./_fake-dom.js";

class FakeListener {
  supported = true;
  isListening = false;
  setCallbacks(callbacks) {
    this.callbacks = callbacks;
  }
  async start() {
    this.isListening = true;
    this.callbacks.onStateChange();
    return true;
  }
  stop() {
    this.isListening = false;
    this.callbacks.onStateChange();
  }
  say(text) {
    this.callbacks.onResult(text, true);
  }
}

function controller() {
  const doc = new FakeDocument();
  const textarea = doc.add(new FakeElement("textarea", doc));
  const status = doc.add(new FakeElement("div", doc));
  const button = doc.add(new FakeElement("button", doc));
  const listener = new FakeListener();
  const spoken = [];
  let opened = 0;
  let saves = 0;
  let name = "";
  const instance = new HandsFreeNotesController({
    listener,
    textarea,
    status,
    toggleButton: button,
    openNew: () => {
      opened += 1;
      textarea.value = "";
    },
    setName: (value) => {
      name = value;
    },
    save: async () => {
      saves += 1;
      return true;
    },
    speak: (text) => spoken.push(text),
  }).bind();
  return {
    instance,
    listener,
    textarea,
    status,
    button,
    spoken,
    get name() {
      return name;
    },
    get opened() {
      return opened;
    },
    get saves() {
      return saves;
    },
  };
}

describe("hands-free Notes", () => {
  test("activation, naming, dictation, stop, and save are separate commands", async () => {
    const page = controller();
    await page.instance.toggle();
    page.listener.say("open notes");
    page.listener.say("Name it Shopping list");
    page.listener.say("start taking notes");
    page.listener.say("voice commands must not be inserted");
    page.listener.say("stop taking notes");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(page.opened).toBe(1);
    expect(page.name).toBe("Shopping list");
    expect(page.textarea.value).toBe("voice commands must not be inserted");
    expect(page.saves).toBe(1);
    expect(page.spoken).toEqual([
      "Toyota voice listener on",
      "What would you like to name the note?",
      "Named Shopping list",
      "Recording notes",
      "Recording stopped. Note saved",
    ]);
    expect(page.status.textContent).toBe("Recording stopped. Note saved");
  });

  test("repeated open commands do not create duplicate notes and stop leaves voice session usable", async () => {
    const page = controller();
    await page.instance.toggle();
    page.listener.say("open note for me");
    page.listener.say("open note for me");
    page.listener.say("start taking notes");
    page.listener.say("hello");
    page.listener.say("I'm finished");
    expect(page.opened).toBe(1); // repeated commands are idempotent until a save creates the note
    expect(page.textarea.value).toBe("hello");
    expect(page.listener.isListening).toBe(true);
    page.instance.toggle();
    expect(page.listener.isListening).toBe(false);
  });

  test("Toyota on/off intents change the voice-session state", async () => {
    const page = controller();
    await page.instance.toggle();
    page.listener.say("Turn Toyota off");
    expect(page.listener.isListening).toBe(false);
    page.listener.say("Turn Toyota on");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(page.listener.isListening).toBe(true);
  });

  test("a failed stop/save never claims that the note was saved", async () => {
    const page = controller();
    page.instance._save = async () => false;
    await page.instance.toggle();
    page.listener.say("start taking notes");
    page.listener.say("Okay, I'm done taking notes");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(page.status.textContent).toContain("could not be saved");
    expect(page.spoken).not.toContain("Recording stopped. Note saved");
  });

  test("unsupported recognition is reported without changing the note", async () => {
    const page = controller();
    page.listener.supported = false;
    await page.instance.toggle();
    expect(page.status.textContent).toContain("not supported");
    expect(page.textarea.value).toBe("");
  });
});
