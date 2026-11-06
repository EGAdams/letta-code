import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesAlertList,
  propertiesAlertList,
} from "./alert-list.observed-attributes.js";

export const alertListDefine = () =>
  defineOnce(
    "alert-list",
    wrap(
      () => import("./alert-list.component.js"),
      "AlertList",
      observedAttributesAlertList,
      propertiesAlertList,
    ),
  );
