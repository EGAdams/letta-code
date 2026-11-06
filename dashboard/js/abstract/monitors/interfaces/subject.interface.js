/**
 * ISubject — the-factory's ISubject (observers / attach / detach / notify).
 * Concrete on purpose: every monitor source shares this bookkeeping.
 */
export class ISubject {
  constructor() {
    this.observers = [];
  }

  /** @param {import("./observer.interface.js").IObserver} observer */
  attach(observer) {
    if (!this.observers.includes(observer)) this.observers.push(observer);
  }

  detach(observer) {
    this.observers = this.observers.filter((o) => o !== observer);
  }

  notify() {
    for (const observer of [...this.observers]) {
      try {
        observer.update(this);
      } catch (error) {
        console.warn("[monitors] observer failed:", error);
      }
    }
  }
}
