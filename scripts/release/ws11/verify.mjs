#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { evaluateDossier, exitCodeFor } from "./evaluate.mjs";
import { REPO_ROOT, buildInventory, buildSbom } from "./inventory.mjs";
import { allGenerated } from "./characterize.mjs";
import { stableStringify } from "./stable.mjs";

const DOSSIER_NAMES = new Set(["optics-public.json", "phantom-engine-private.json", "private-customer.json"]);

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) out[key] = true;
    else {
      out[key] = next;
      i += 1;
    }
  }
  return out;
}

function emitGenerated(root) {
  const { artifacts, evaluations } = allGenerated(root);
  artifacts["evaluations.json"] = evaluations;
  for (const [name, value] of Object.entries(artifacts)) {
    const dir = DOSSIER_NAMES.has(name)
      ? join(root, "docs/programs/release-engineering/dossiers")
      : join(root, "docs/programs/release-engineering/generated");
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, name), stableStringify(value));
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = REPO_ROOT;
  if (args.emit === true) {
    emitGenerated(root);
    process.stdout.write("WS11_EMIT ok\n");
    return;
  }
  if (args.inventory === true) {
    process.stdout.write(stableStringify(buildInventory(root)));
    return;
  }
  if (args.sbom === true) {
    process.stdout.write(stableStringify(buildSbom(root)));
    return;
  }
  if (typeof args.dossier === "string") {
    const dossier = JSON.parse(readFileSync(args.dossier, "utf8"));
    const result = evaluateDossier(dossier, { root });
    process.stdout.write(stableStringify(result));
    process.exit(exitCodeFor(result));
  }
  process.stderr.write("vantio-ws11: pass --dossier, --inventory, --sbom, or --emit\n");
  process.exit(1);
}

main();
