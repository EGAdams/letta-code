import { abstractMethod } from "../../not-implemented.js";

/**
 * IObserver — the-factory's IObserver, in plain JS.
 * An observer is told which subject changed; it reads what it needs from it.
 */
export class IObserver {
  /** @param {import("./subject.interface.js").ISubject} _subject */
  update(_subject) {
    abstractMethod("update");
  }
}
