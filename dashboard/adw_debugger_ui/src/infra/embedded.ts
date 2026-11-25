// Adapters for a diagram embedded in another page: there is no dashboard
// terminal to hide, and nothing is cleared, so nothing needs remembering.
import type { IClearStore, ILegacyTerminal } from "../contracts";

export class NoLegacyTerminal implements ILegacyTerminal {
  setVisible(): void {}
}

export class NothingCleared implements IClearStore {
  get(): number {
    return 0;
  }
  set(): void {}
}
