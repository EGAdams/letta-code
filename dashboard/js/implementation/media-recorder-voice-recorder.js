import { VoiceRecorder } from "../abstract/voice-recorder.interface.js";
import { HttpVoiceMediaClient } from "./voice_media/dist/http-voice-media-client.js";

/**
 * MediaRecorderVoiceRecorder — concrete VoiceRecorder bound to the browser
 * capture stack. The state machine (idle → recording → processing → idle) lives
 * in the base class; this binds the four device primitives:
 *
 *   openStream   → navigator.mediaDevices.getUserMedia({ audio:true })
 *   beginCapture → new MediaRecorder(stream).start()
 *   endCapture   → recorder.stop() → assemble a Blob from the chunks
 *   transcribe   → pass the blob to an injected VoiceMediaClient
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
    mediaClient = null,
  } = {}) {
    super({ onStateChange });
    this._navigator = nav;
    this._Recorder = Recorder;
    this._Blob = BlobCtor;
    this._mediaClient =
      mediaClient ||
      new HttpVoiceMediaClient({ fetch: fetchFn, endpoint, filename });
    this._stream = null;
    this._recorder = null;
    this._chunks = [];
  }

  /** @override Acquire a mic stream and arm a MediaRecorder. */
  async openStream() {
    const media = this._navigator?.mediaDevices;
    if (!media || !media.getUserMedia) {
      this._lastError =
        "Microphone needs a secure context (https). Open this dashboard via the Tailscale https URL.";
      return false;
    }
    try {
      this._stream = await media.getUserMedia({ audio: true });
    } catch (e) {
      this._lastError =
        e?.name === "NotAllowedError" || e?.name === "SecurityError"
          ? "Microphone permission was denied. Check Chrome's site permission and, on Android, Settings → Apps → Chrome → Permissions → Microphone."
          : e?.name === "NotFoundError"
            ? "No microphone was found."
            : `Microphone unavailable: ${e?.message || e?.name || "unknown error"}`;
      return false;
    }
    try {
      this._recorder = new this._Recorder(this._stream);
    } catch (error) {
      this._releaseStream();
      throw error;
    }
    return true;
  }

  _releaseStream() {
    for (const track of this._stream?.getTracks?.() || []) track.stop();
    this._stream = null;
  }

  /** @override Start buffering audio chunks. */
  beginCapture() {
    this._chunks = [];
    this._recorder.ondataavailable = (e) => {
      if (e?.data?.size) this._chunks.push(e.data);
    };
    try {
      this._recorder.start();
    } catch (error) {
      this._releaseStream();
      this._recorder = null;
      throw error;
    }
  }

  /** @override Stop the recorder, release tracks, resolve the recorded blob. */
  endCapture() {
    return new Promise((resolve) => {
      const finish = () => {
        this._releaseStream();
        const type = this._recorder?.mimeType || "audio/webm";
        resolve(new this._Blob(this._chunks, { type }));
      };
      this._recorder.onstop = finish;
      if (this._recorder.state !== "inactive") {
        try {
          this._recorder.stop();
        } catch (error) {
          this._releaseStream();
          throw error;
        }
      } else finish();
    });
  }

  /** @override Resolve a validated transcript through the media port. */
  async transcribe(blob) {
    return this._mediaClient.transcribe(blob);
  }
}
