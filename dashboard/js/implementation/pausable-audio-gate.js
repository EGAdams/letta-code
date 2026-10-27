/**
 * PausableAudioGate — a Pause/Play hold over a speech synthesizer's audio.
 *
 * GoF: Proxy. It sits on EdgeTtsSpeechSynthesizer's injected `audioFactory`
 * seam, so the synthesizer is untouched: every Audio element it creates comes
 * from `gate.audioFactory`, and the gate decides whether `play()` really runs.
 *
 *   pause()  — the playing clip stops where it is; any clip that arrives while
 *              paused is fetched but held before its first sample.
 *   resume() — the stopped clip carries on from the same point, or the held
 *              clip starts.
 *
 * Because the speech queue waits for each clip's `ended`, holding one clip
 * holds the rest of the reply behind it — nothing is skipped or lost.
 *
 * The synthesizer's own cancel() calls `audio.pause()` on a clip it is
 * dropping. That rejects the clip's outstanding play() so the synthesizer's
 * in-flight speak() settles instead of hanging forever.
 *
 * The play() the synthesizer sees belongs to the gate, not the browser. A
 * Pause pressed while a clip is still loading makes the browser reject its
 * play() ("interrupted by a call to pause()"); the synthesizer would read
 * that as a failure and drop the reply. The gate absorbs that rejection and
 * keeps waiting for Play instead.
 *
 * Starts paused by default so Toyota never talks before someone asks her to.
 */
export class PausableAudioGate {
  /**
   * @param {object} [opts]
   * @param {boolean} [opts.paused=true]
   * @param {(url:string)=>object} [opts.createAudio] builds the real element.
   */
  constructor({
    paused = true,
    createAudio = (url) => new globalThis.Audio(url),
  } = {}) {
    this._paused = paused;
    this._createAudio = createAudio;
    this._current = null; // { audio, realPlay, realPause, waiter, attempts, ended }
    this._listeners = new Set();
    this.audioFactory = (url) => this._wrap(this._createAudio(url));
  }

  get paused() {
    return this._paused;
  }

  /** @param {(paused:boolean)=>void} fn  @returns {()=>void} unsubscribe */
  onChange(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  pause() {
    if (this._paused) return;
    this._paused = true;
    const cur = this._current;
    if (cur && !cur.ended) {
      try {
        cur.realPause();
      } catch {
        // element already gone
      }
    }
    this._emit();
  }

  resume() {
    if (!this._paused) return;
    this._paused = false;
    const cur = this._current;
    if (cur?.waiter) this._start(cur);
    else if (cur && !cur.ended)
      Promise.resolve()
        .then(() => cur.realPlay())
        .catch(() => {});
    this._emit();
  }

  toggle() {
    if (this._paused) this.resume();
    else this.pause();
  }

  _emit() {
    for (const fn of this._listeners) {
      try {
        fn(this._paused);
      } catch {
        // a listener must never break playback
      }
    }
  }

  /** Ask the browser to play; settle the synthesizer's play() on success. */
  _start(entry) {
    const attempt = ++entry.attempts;
    Promise.resolve()
      .then(() => entry.realPlay())
      .then(
        () => {
          const waiter = entry.waiter;
          entry.waiter = null;
          waiter?.resolve();
        },
        (err) => {
          // Our own Pause interrupted the load: keep waiting for Play.
          if (attempt !== entry.attempts || this._paused) return;
          const waiter = entry.waiter;
          entry.waiter = null;
          waiter?.reject(err);
        },
      );
  }

  _wrap(audio) {
    const entry = {
      audio,
      realPlay: audio.play.bind(audio),
      realPause: audio.pause.bind(audio),
      waiter: null,
      attempts: 0,
      ended: false,
    };
    this._current = entry;
    audio.addEventListener?.("ended", () => {
      entry.ended = true;
      if (this._current === entry) this._current = null;
    });
    audio.play = () =>
      new Promise((resolve, reject) => {
        entry.waiter = { resolve, reject };
        if (!this._paused) this._start(entry);
      });
    // The synthesizer pauses a clip only when it is dropping it.
    audio.pause = () => {
      if (this._current === entry) this._current = null;
      entry.attempts += 1; // ignore any start still in flight
      const waiter = entry.waiter;
      entry.waiter = null;
      waiter?.reject(new Error("speech cancelled"));
      entry.realPause();
    };
    return audio;
  }
}
