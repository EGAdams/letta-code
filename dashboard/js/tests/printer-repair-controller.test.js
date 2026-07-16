import { describe, expect, test } from "bun:test";
import {
  buildPrinterRepairRequest,
  PrinterRepairController,
} from "../implementation/printer-repair-controller.js";

const fakeHttp = (result) => {
  const calls = [];
  return {
    calls,
    postJSON: async (url, body) => {
      calls.push({ url, body });
      if (result instanceof Error) throw result;
      return result;
    },
  };
};

describe("PrinterRepairController", () => {
  test("builds the printer repair request", () => {
    expect(buildPrinterRepairRequest()).toEqual({
      url: "/api/fix-printer",
      body: {},
    });
  });

  test("requires an HttpClient", () => {
    expect(() => new PrinterRepairController()).toThrow(/requires/);
    expect(() => new PrinterRepairController({ http: {} })).toThrow(/requires/);
  });

  test("posts the repair and returns the backend result", async () => {
    const http = fakeHttp({
      ok: true,
      text: "Printer fixed. Windows status: Normal.",
      status: "Normal",
    });
    const controller = new PrinterRepairController({ http });

    const result = await controller.repair();

    expect(http.calls).toEqual([{ url: "/api/fix-printer", body: {} }]);
    expect(result.status).toBe("Normal");
    expect(result.ok).toBe(true);
  });

  test("turns transport failures into a visible result", async () => {
    const controller = new PrinterRepairController({
      http: fakeHttp(new Error("HTTP 502")),
    });
    expect(await controller.repair()).toEqual({
      ok: false,
      text: "HTTP 502",
    });
  });
});
