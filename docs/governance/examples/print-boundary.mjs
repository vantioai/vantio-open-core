import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..");
const boundary = JSON.parse(readFileSync(join(root, "docs/governance/PRODUCT-BOUNDARY.json"), "utf8"));
const readme = readFileSync(join(root, boundary.readme), "utf8");

for (const phrase of boundary.required_phrases) {
  if (!readme.includes(phrase)) {
    process.stderr.write(`missing phrase: ${phrase}\n`);
    process.exit(1);
  }
}

process.stdout.write("vantio-optics-boundary-ok\n");
