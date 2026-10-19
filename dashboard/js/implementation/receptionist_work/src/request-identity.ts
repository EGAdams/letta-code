import type { RequestIdentity } from "./interfaces.js";

/** getRandomValues also works on the dashboard's plain HTTP LAN origin. */
export function newBrowserRequestId(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

/** Adapter: transient voice generations never become persistent operation IDs. */
export class TurnRequestIdentity implements RequestIdentity {
  private readonly ids = new Map<string, string>();
  constructor(private readonly create: () => string) {}
  forGeneration(generation: string): string {
    const known = this.ids.get(generation);
    if (known) return known;
    const id = this.create();
    this.ids.set(generation, id);
    if (this.ids.size > 64) this.ids.delete(this.ids.keys().next().value!);
    return id;
  }
}
