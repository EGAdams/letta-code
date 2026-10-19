import type {
  IWorkflowCheckpoint,
  IWorkflowEvidenceSource,
  IWorkflowRun,
} from "../../../../../the-factory/src/components/workflow-inspector/interfaces";
import { decodeCheckpoint, decodeRun, runId } from "./decoders";
import type { IReadJson } from "./interfaces";

/** Adapter: existing dashboard read routes supply the reusable library port. */
export class ReceptionistEvidenceSource implements IWorkflowEvidenceSource {
  constructor(private readonly http: IReadJson) {}
  async checkpoint(signal: AbortSignal): Promise<IWorkflowCheckpoint> {
    return decodeCheckpoint(
      await this.http.get("/api/receptionist-work", {
        method: "GET",
        cache: "no-store",
        signal,
      }),
    );
  }
  async run(id: string, signal: AbortSignal): Promise<IWorkflowRun> {
    const checked = runId(id);
    return decodeRun(
      await this.http.get(`/api/receptionist-work/trace?run=${checked}`, {
        method: "GET",
        cache: "no-store",
        signal,
      }),
      checked,
    );
  }
}

export class BrowserReadJson implements IReadJson {
  async get(url: string, options: RequestInit): Promise<unknown> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    if (options.signal?.aborted) abort();
    const timeout = setTimeout(abort, 15000);
    try {
      const response = await fetch(url, {
        ...options,
        method: "GET",
        signal: controller.signal,
      });
      if (!response.ok)
        throw new Error(
          `Evidence unavailable (HTTP ${response.status}). Refresh to retry.`,
        );
      return await response.json();
    } catch (error) {
      if (controller.signal.aborted)
        throw new Error(
          "Evidence request stopped or timed out. Refresh to retry.",
        );
      throw error;
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}
