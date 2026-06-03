// Dual-package fixup: the SDK ships both an ESM build (dist/esm) and a CJS
// build (dist/cjs) from a package.json that has NO top-level "type" field.
// Without per-directory "type" markers Node would parse dist/esm/index.js
// (which uses ESM `import` syntax) as CommonJS and throw a SyntaxError.
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
