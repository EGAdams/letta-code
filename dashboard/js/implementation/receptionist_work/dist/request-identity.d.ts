import type { RequestIdentity } from "./interfaces.js";
/** getRandomValues also works on the dashboard's plain HTTP LAN origin. */
export declare function newBrowserRequestId(): string;
/** Adapter: transient voice generations never become persistent operation IDs. */
export declare class TurnRequestIdentity implements RequestIdentity {
  private readonly create;
  private readonly ids;
  constructor(create: () => string);
  forGeneration(generation: string): string;
}
