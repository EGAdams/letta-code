import type { WorkState } from "./contracts.js";
import type { WorkFacts, WorkPresenter } from "./interfaces.js";
/**
 * Presenter: turns one checkpoint into the separate statements the work panel shows. It exists so
 * that "waiting", "cancelled", "failed" and "verified" can never collapse into one hopeful line of
 * text, and so a claim of success always arrives with the identity of the run that earned it.
 */
export declare class TrainingWorkPresenter implements WorkPresenter {
  present(state: WorkState): WorkFacts;
  private evidence;
}
