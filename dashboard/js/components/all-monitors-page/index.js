import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesAllMonitorsPage,
  propertiesAllMonitorsPage,
} from "./all-monitors-page.observed-attributes.js";

export const allMonitorsPageDefine = () =>
  defineOnce(
    "all-monitors-page",
    wrap(
      () => import("./all-monitors-page.component.js"),
      "AllMonitorsPage",
      observedAttributesAllMonitorsPage,
      propertiesAllMonitorsPage,
    ),
  );
