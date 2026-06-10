import { VoiceRecorder } from "../abstract/voice-recorder.interface.js";

/**
 * MediaRecorderVoiceRecorder — concrete VoiceRecorder bound to the browser
 * capture stack. The state machine (idle → recording → processing → idle) lives
 * in the base class; this binds the four device primitives:
 *
 *   openStream   → navigator.mediaDevices.getUserMedia({ audio:true })
 *   beginCapture → new MediaRecorder(stream).start()
 *   endCapture   → recorder.stop() → assemble a Blob from the chunks
 *   transcribe   → POST the blob to /api/voice, return the parsed payload
 *
 * Every browser dependency is injectable so the whole flow is unit-testable.
 */
export class MediaRecorderVoiceRecorder extends VoiceRecorder {
  constructor({
    onStateChange,
    navigator: nav = globalThis.navigator,
    MediaRecorder: Recorder = globalThis.MediaRecorder,
    Blob: BlobCtor = globalThis.Blob,
    fetch: fetchFn = globalThis.fetch?.bind(globalThis),
    endpoint = "/api/voice",
    filename = "voice.webm",
  } = {}) {
    super({ onStateChange });
    this._navigator = nav;
    this._Recorder = Recorder;
    this._Blob = BlobCtor;
    this._fetch = fetchFn;
    this._endpoint = endpoint;
    this._filename = filename;
    this._stream = null;
    this._recorder = null;
    this._chunks = [];
  }

  /** @override Acquire a mic stream and arm a MediaRecorder. */
  async openStream() {
    const media = this._navigator?.mediaDevices;
    if (!media || !media.getUserMedia) return false; // needs a secure context
    try {
      this._stream = await media.getUserMedia({ audio: true });
    } catch {
      return false; // permission denied / unavailable
    }
    this._recorder = new this._Recorder(this._stream);
    return true;
  }

  /** @override Start buffering audio chunks. */
  beginCapture() {
    this._chunks = [];
    this._recorder.ondataavailable = (e) => {
      if (e?.data?.size) this._chunks.push(e.data);
    };
    this._recorder.start();
  }

  /** @override Stop the recorder, release tracks, resolve the recorded blob. */
  endCapture() {
    return new Promise((resolve) => {
      const finish = () => {
        if (this._stream?.getTracks) {
          for (const t of this._stream.getTracks()) t.stop();
        }
        const type = this._recorder?.mimeType || "audio/webm";
        resolve(new this._Blob(this._chunks, { type }));
      };
      this._recorder.onstop = finish;
      if (this._recorder.state !== "inactive") this._recorder.stop();
      else finish();
    });
  }

  /** @override Upload the blob; resolve the parsed voice payload or throw. */
  async transcribe(blob) {
    const res = await this._fetch(this._endpoint, {
      method: "POST",
      headers: { "X-Filename": this._filename },
      body: blob,
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "voice processing failed");
    return data;
  }
}
