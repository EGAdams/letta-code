import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesStatusDonut,
  propertiesStatusDonut,
} from "./status-donut.observed-attributes.js";

export const statusDonutDefine = () =>
  defineOnce(
    "status-donut",
    wrap(
      () => import("./status-donut.component.js"),
      "StatusDonut",
      observedAttributesStatusDonut,
      propertiesStatusDonut,
    ),
  );
