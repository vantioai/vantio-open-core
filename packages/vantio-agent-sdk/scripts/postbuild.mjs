// Dual-package fixup: the SDK ships both an ESM build (dist/esm) and a CJS
// build (dist/cjs). The root package.json's top-level "type" (set to
// "module" so `src/`/`test/` run natively as ESM under Node's built-in
// TypeScript support) has no bearing on either build directory — Node
// resolves the nearest package.json to each file, so without per-directory
// "type" markers here dist/cjs/index.js would incorrectly inherit "module"
// and throw a SyntaxError on its CommonJS `exports.foo = ...` syntax.
//
// Emitting dist/esm/package.json {"type":"module"} and
// dist/cjs/package.json {"type":"commonjs"} pins each build to the correct
// module system regardless of the parent package's resolution.
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, "..", "dist");

const markers = [
  ["esm", "module"],
  ["cjs", "commonjs"],
];

for (const [sub, type] of markers) {
  const dir = join(distDir, sub);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "package.json"), JSON.stringify({ type }, null, 2) + "\n");
}
