import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesTrendSparkline,
  propertiesTrendSparkline,
} from "./trend-sparkline.observed-attributes.js";

export const trendSparklineDefine = () =>
  defineOnce(
    "trend-sparkline",
    wrap(
      () => import("./trend-sparkline.component.js"),
      "TrendSparkline",
      observedAttributesTrendSparkline,
      propertiesTrendSparkline,
    ),
  );
