import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesMonitorCard,
  propertiesMonitorCard,
} from "./monitor-card.observed-attributes.js";

export const monitorCardDefine = () =>
  defineOnce(
    "monitor-card",
    wrap(
      () => import("./monitor-card.component.js"),
      "MonitorCard",
      observedAttributesMonitorCard,
      propertiesMonitorCard,
    ),
  );
