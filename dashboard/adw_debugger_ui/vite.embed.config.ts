import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// The embeddable one-run diagram: its own folder, so neither build empties the other's.
export default defineConfig({
  plugins: [vue()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../js/adw-run-sequence",
    emptyOutDir: true,
    lib: {
      entry: "src/embed.ts",
      formats: ["es"],
      fileName: () => "adw-run-sequence.js",
    },
    rollupOptions: { output: { assetFileNames: "adw-run-sequence[extname]" } },
  },
});
