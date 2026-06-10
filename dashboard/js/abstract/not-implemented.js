/**
 * NotImplementedError — the contract-enforcement primitive for every abstract
 * interface in this directory.
 *
 * JavaScript has no native `interface` keyword, so we emulate GoF-style abstract
 * types with base classes whose "primitive operations" call `abstractMethod()`.
 * A concrete subclass in js/implementation/ MUST override each primitive; if it
 * forgets, the call fails loudly instead of silently doing nothing.
 */
export class NotImplementedError extends Error {
  constructor(method) {
    super(`${method}() is abstract and must be implemented by a subclass`);
    this.name = "NotImplementedError";
  }
}

/** Throw from an abstract primitive operation. */
export function abstractMethod(name) {
  throw new NotImplementedError(name);
}
