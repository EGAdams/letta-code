import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesMonitorLedView,
  propertiesMonitorLedView,
} from "./monitor-led.observed-attributes.js";

export const monitorLedDefine = () =>
  defineOnce(
    "monitor-led",
    wrap(
      () => import("./monitor-led.component.js"),
      "MonitorLedView",
      observedAttributesMonitorLedView,
      propertiesMonitorLedView,
    ),
  );
