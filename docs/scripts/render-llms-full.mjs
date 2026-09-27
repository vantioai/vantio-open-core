import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { readJson, renderLlmsFull } from "./docs-release-lib.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const manifest = readJson(root, "docs/governance/MANIFEST.json");
writeFileSync(join(root, manifest.llms_full_txt), renderLlmsFull(root, manifest.canonical_docs));
process.stdout.write(`${manifest.llms_full_txt}\n`);
