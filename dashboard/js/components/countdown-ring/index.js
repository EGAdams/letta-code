import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesCountdownRing,
  propertiesCountdownRing,
} from "./countdown-ring.observed-attributes.js";

export const countdownRingDefine = () =>
  defineOnce(
    "countdown-ring",
    wrap(
      () => import("./countdown-ring.component.js"),
      "CountdownRing",
      observedAttributesCountdownRing,
      propertiesCountdownRing,
    ),
  );
