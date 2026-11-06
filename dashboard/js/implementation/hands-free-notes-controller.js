/**
 * Hands-free Notes controller.
 *
 * The listener is injected so Toyota (or another adapter) can feed the same
 * command/state machine. Commands are consumed separately from note text.
 */
const COMMANDS = Object.freeze({
  open: /^(?:open notes?|open a new note|open note for me)\.?$/i,
  start: /^start taking notes\.?$/i,
  stop: /^(?:okay,?\s+)?(?:i'?m\s+(?:finished|done taking notes)|stop taking notes|end recording)\.?$/i,
  on: /^turn toyota on\.?$/i,
  off: /^turn toyota off\.?$/i,
  read: /^read back note\.?$/i,
});

const clean = (value) =>
  String(value || "")
    .trim()
    .replace(/\s+/g, " ");
const matches = (value, pattern) => pattern.test(clean(value));

export class HandsFreeNotesController {
  constructor({
    listener,
    textarea,
    status,
    toggleButton,
    onButton,
    offButton,
    recordButton,
    stopButton,
    openNew,
    setName,
    save,
    read,
    speak = (text) => {
      if (typeof globalThis.speechSynthesis?.speak !== "function") return;
      globalThis.speechSynthesis.cancel?.();
      globalThis.speechSynthesis.speak(
        new globalThis.SpeechSynthesisUtterance(text),
      );
    },
  }) {
    this._listener = listener;
    this._textarea = textarea;
    this._status = status;
    this._toggleButton = toggleButton;
    this._onButton = onButton;
    this._offButton = offButton;
    this._recordButton = recordButton;
    this._stopButton = stopButton;
    this._openNew = openNew;
    this._setName = setName;
    this._save = save;
    this._read = read;
    this._speak = speak;
    this._dictating = false;
    this._newNoteOpen = false;
    this._state = "idle";
    this._bound = false;
  }

  bind() {
    if (this._bound || !this._listener || !this._toggleButton) return this;
    this._bound = true;
    this._listener.setCallbacks({
      onResult: (text, isFinal) => this._onResult(text, isFinal),
      onStateChange: () => this._render(),
      onError: (message) => {
        this._dictating = false;
        this._setStatus(message);
        this._render();
      },
    });
    this._toggleButton.addEventListener("click", () => this.toggle());
    this._onButton?.addEventListener("click", () => this.turnOn());
    this._offButton?.addEventListener("click", () => this.turnOff());
    this._recordButton?.addEventListener("click", () => this.startRecording());
    this._stopButton?.addEventListener(
      "click",
      () => void this.stopRecording(),
    );
    this._render();
    return this;
  }

  async turnOn() {
    if (this._listener.isListening) return true;
    if (!this._listener.supported) {
      this._setStatus("Voice commands are not supported in this browser.");
      return false;
    }
    const started = await this._listener.start();
    if (!started) {
      this._setStatus(
        "Could not start Toyota voice listener. Check microphone permission.",
      );
      return false;
    }
    this._setStatus("Toyota voice listener on.");
    this._speak("Toyota voice listener on");
    this._render();
    return true;
  }

  turnOff() {
    if (this._listener.isListening) this._listener.stop();
    this._dictating = false;
    this._state = "idle";
    this._setStatus(
      "Toyota voice listener off. Use the button or an always-on wake-word bridge to turn it on.",
    );
    this._render();
    return true;
  }

  async toggle() {
    if (this._listener.isListening) return this.turnOff();
    return this.turnOn();
  }

  async startRecording() {
    this._dictating = true;
    this._state = "dictating";
    this._setStatus("Recording notes…");
    this._speak("Recording notes");
  }

  async stopRecording() {
    this._dictating = false;
    this._state = "saving";
    this._setStatus("Stopping recording and saving note…");
    try {
      const saved = await this._save();
      if (saved === false) throw new Error("save failed");
      this._state = "idle";
      this._newNoteOpen = false;
      this._setStatus("Recording stopped. Note saved.");
      this._speak("Recording stopped. Note saved.");
      return true;
    } catch {
      this._state = "error";
      this._setStatus("Recording stopped, but the note could not be saved.");
      this._speak("Recording stopped, but the note could not be saved.");
      return false;
    }
  }

  _setStatus(message) {
    if (this._status) this._status.textContent = message;
  }

  _render() {
    const on = !!this._listener?.isListening;
    this._toggleButton.textContent = on
      ? "Stop Toyota Voice"
      : "Start Toyota Voice";
    this._toggleButton.classList.toggle("recording", on);
    this._toggleButton.setAttribute("aria-pressed", String(on));
    this._toggleButton.setAttribute(
      "aria-label",
      on ? "Turn Toyota voice off" : "Turn Toyota voice on",
    );
  }

  _onResult(text, isFinal) {
    if (!isFinal) return;
    const phrase = clean(text);
    if (!phrase) return;
    if (matches(phrase, COMMANDS.off)) {
      this.turnOff();
    } else if (matches(phrase, COMMANDS.on)) {
      void this.turnOn();
    } else if (this._dictating && matches(phrase, COMMANDS.stop)) {
      void this.stopRecording();
    } else if (matches(phrase, COMMANDS.open)) {
      this._dictating = false;
      if (!this._newNoteOpen) {
        this._state = "naming";
        this._openNew();
        this._newNoteOpen = true;
      }
      this._setStatus("What would you like to name the note?");
      this._speak("What would you like to name the note?");
    } else if (matches(phrase, COMMANDS.start)) {
      void this.startRecording();
    } else if (matches(phrase, COMMANDS.read)) {
      this._read?.();
    } else if (this._state === "naming") {
      const name = phrase.replace(/^name (?:it|the note)\s+/i, "").trim();
      if (!name) return;
      this._setName?.(name);
      this._state = "idle";
      this._setStatus(`Named ${name}`);
      this._speak(`Named ${name}`);
    } else if (this._dictating) {
      const separator =
        this._textarea.value && /\s$/.test(this._textarea.value) ? "" : " ";
      this._textarea.value += separator + phrase;
      this._textarea.dispatch("input");
    }
  }

  stop() {
    this._dictating = false;
    this._state = "idle";
    if (this._listener?.isListening) this._listener.stop();
    this._render();
  }
}

export { COMMANDS };
