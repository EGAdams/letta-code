// Strategy: which run the view follows.
//
//   running run selected    -> stay on it; a second running run never steals the view
//   failed / interrupted    -> pinned until Follow live releases it
//   succeeded, or nothing   -> the earliest-started running run (run id breaks a tie);
//                              with none running, the newest run that started after the
//                              selected one (it ran to its end between two reads of the
//                              feed); otherwise stay put, or show the latest finished run
import type {
  IRunSelectionPolicy,
  RunMode,
  RunSelection,
  RunSummary,
} from "../contracts";

function byStart(a: RunSummary, b: RunSummary): number {
  return (
    a.startedAt.localeCompare(b.startedAt) || a.runId.localeCompare(b.runId)
  );
}

function failed(run: RunSummary | undefined): boolean {
  return run?.status === "fail" || run?.status === "interrupted";
}

export class EarliestActiveRunPolicy implements IRunSelectionPolicy {
  select(current: RunSelection, runs: RunSummary[]): RunSelection {
    const selected = runs.find((run) => run.runId === current.runId);
    if (selected?.status === "running") return current;
    if (failed(selected) && !current.pinReleased) return current;
    const active = runs
      .filter((run) => run.status === "running")
      .sort(byStart)[0];
    if (active) return { runId: active.runId, pinReleased: false };
    const latest = [...runs].sort(byStart).at(-1);
    if (selected && (!latest || byStart(latest, selected) <= 0)) return current;
    return { runId: latest?.runId ?? null, pinReleased: false };
  }

  followLive(current: RunSelection, runs: RunSummary[]): RunSelection {
    return this.select({ runId: current.runId, pinReleased: true }, runs);
  }

  mode(selection: RunSelection, runs: RunSummary[]): RunMode {
    const selected = runs.find((run) => run.runId === selection.runId);
    if (!selected) return "idle";
    if (selected.status === "running") return "live";
    return failed(selected) && !selection.pinReleased ? "pinned" : "completed";
  }
}

// Strategy: the freshest run is the one on screen.
//
//   any run starts           -> it takes the view, whatever was there before
//   nothing newer has begun  -> stay on the selected run, finished or not, so a
//                               failure stays readable until the next ADW starts
//   on attach                -> the newest run recorded
//
// "Newest" is by start time, run id breaking a tie, so it agrees with the order
// the ADWs were launched in rather than the order their events arrived.
export class NewestRunPolicy implements IRunSelectionPolicy {
  select(current: RunSelection, runs: RunSummary[]): RunSelection {
    const newest = [...runs].sort(byStart).at(-1);
    if (!newest) return { runId: null, pinReleased: false };
    if (newest.runId === current.runId) return current;
    return { runId: newest.runId, pinReleased: false };
  }

  followLive(current: RunSelection, runs: RunSummary[]): RunSelection {
    return this.select(current, runs);
  }

  mode(selection: RunSelection, runs: RunSummary[]): RunMode {
    const selected = runs.find((run) => run.runId === selection.runId);
    if (!selected) return "idle";
    return selected.status === "running" ? "live" : "completed";
  }
}
