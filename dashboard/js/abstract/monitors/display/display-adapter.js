import { abstractMethod } from "../../not-implemented.js";

/** DisplayAdapter — Oak Ridge's Strategy for showing the reading beside a gauge. */
export class DisplayAdapter {
  update(_currentValue) {
    abstractMethod("update");
  }
}
