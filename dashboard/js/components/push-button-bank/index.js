import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import {
  observedAttributesPushButtonBank,
  propertiesPushButtonBank,
} from "./push-button-bank.observed-attributes.js";

export const pushButtonBankDefine = () =>
  defineOnce(
    "push-button-bank",
    wrap(
      () => import("./push-button-bank.component.js"),
      "PushButtonBank",
      observedAttributesPushButtonBank,
      propertiesPushButtonBank,
    ),
  );
