import { dirname, resolve } from "node:path";

/** Bundle directly from the shared library; no hand-copied component implementation. */
async function inlineStyles(path: string): Promise<string> {
  let text = await Bun.file(path).text();
  for (const match of text.matchAll(/@import\s+["']([^"']+)["'];/g)) {
    text = text.replace(
      match[0],
      await inlineStyles(resolve(dirname(path), match[1]!)),
    );
  }
  return text;
}

const result = await Bun.build({
  entrypoints: [resolve(import.meta.dir, "src/main.ts")],
  outdir: resolve(import.meta.dir, "dist"),
  naming: "manual.js",
  target: "browser",
  format: "esm",
  minify: false,
  tsconfig: resolve(import.meta.dir, "tsconfig.json"),
  plugins: [
    {
      name: "component-templates",
      setup(build) {
        build.onLoad({ filter: /\.(html|css)$/ }, async (args) => ({
          contents: args.path.endsWith(".css")
            ? await inlineStyles(args.path)
            : await Bun.file(args.path).text(),
          loader: "text",
        }));
      },
    },
  ],
});
if (!result.success) {
  for (const log of result.logs) console.error(log);
  process.exit(1);
}
console.log(
  "Built training/dist/manual.js from the-factory TypeScript components.",
);
