import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesRadialGaugeView,
  propertiesRadialGaugeView,
} from "./radial-gauge-view.observed-attributes.js";

export const radialGaugeViewDefine = () =>
  defineOnce(
    "radial-gauge-view",
    wrap(
      () => import("./radial-gauge-view.component.js"),
      "RadialGaugeView",
      observedAttributesRadialGaugeView,
      propertiesRadialGaugeView,
    ),
  );
