import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

// One self-contained ES module (Vue included) plus one stylesheet, written to
// where the dashboard's static fallthrough already serves files from.
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  // Library builds do not replace this on their own; tests must stay in dev mode.
  define:
    mode === "test"
      ? {}
      : { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../js/adw-debugger",
    emptyOutDir: true,
    lib: {
      entry: "src/main.ts",
      formats: ["es"],
      fileName: () => "adw-debugger.js",
    },
    rollupOptions: { output: { assetFileNames: "adw-debugger[extname]" } },
  },
  test: {
    environment: "happy-dom",
    globals: true,
    include: ["tests/**/*.test.ts"],
  },
}));
