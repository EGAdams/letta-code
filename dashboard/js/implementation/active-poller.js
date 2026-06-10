/**
 * ActivePoller — small lifecycle holder for "only one stream polls at a time".
 *
 * The original AM/SM kept a single `pollTimer` and called `stopPoll()` before
 * starting a new stream so switching agent-detail tabs never left two loops
 * running. With per-stream PollingControllers we reproduce that guarantee here:
 * `run(controller)` stops whatever was previously active, then starts the new
 * one. `stop()` halts the current loop (e.g. when leaving the section).
 */
export class ActivePoller {
  constructor() {
    this._current = null;
  }

  /** The controller currently armed, or null. */
  get current() {
    return this._current;
  }

  /** Stop the previous controller (if any) and start this one. */
  async run(controller) {
    if (this._current && this._current !== controller) this._current.stop();
    this._current = controller;
    await controller.start();
    return controller;
  }

  /** Stop and forget the active controller. Safe to call when idle. */
  stop() {
    if (this._current) {
      this._current.stop();
      this._current = null;
    }
  }
}
