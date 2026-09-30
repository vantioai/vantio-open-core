import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { BASE_SHA, PRODUCER_CLASSIFICATION, packJson } from "./framework-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const HASHED = [
  "00-PROGRAM-BOUNDARY.md",
  "01-CLAIM-STAGE-LADDER.md",
  "02-COMPARATOR-RULES.md",
  "03-SCORE.md",
  "04-PERFORMANCE-QUALIFICATION.md",
  "05-INDEPENDENT-COUNCIL.md",
  "CLAIM-LADDER.json",
  "COMPARATOR-MATRIX.json",
  "PERFORMANCE-SCAFFOLD.json",
  "scripts/cell-notes.mjs",
  "scripts/framework-lib.mjs",
  "scripts/check-framework.mjs",
  "scripts/check-framework.test.mjs",
  "scripts/emit-pack.mjs",
];

function sha256(rel) {
  return createHash("sha256").update(readFileSync(join(ROOT, rel))).digest("hex");
}

const documents = packJson();
for (const [name, body] of Object.entries(documents)) {
  const text = name.endsWith(".md") ? body : `${JSON.stringify(body, null, 2)}\n`;
  writeFileSync(join(ROOT, name), text);
}

const files_sha256 = {};
for (const rel of HASHED) {
  if (rel === "scripts/emit-pack.mjs") continue;
  files_sha256[rel] = sha256(rel);
}

const manifest = {
  schema: "vantio.planning.benchmark-framework.manifest/v1",
  audience: "INTERNAL_RESTRICTED",
  document: "BENCHMARK-MANIFEST",
  producer_classification: PRODUCER_CLASSIFICATION,
  producer_role: "PLANNING_PRODUCER_ONLY",
  council_status: "PENDING_INDEPENDENT_COUNCIL",
  council_verdict: null,
  recorded_at_utc: new Date().toISOString(),
  base_sha: BASE_SHA,
  base_subject: "Merge pull request #83 from vantioai/cursor/pe-ws4-vocabulary-binding-f9f5",
  branch: "cursor/benchmark-framework-b6b6",
  repository: "vantioai/vantio-open-core",
  producer: {
    agent: "OMITTED_FROM_PUBLIC_TIP",
    model: "OMITTED_FROM_PUBLIC_TIP",
    url: "OMITTED_FROM_PUBLIC_TIP",
  },
  merge: false,
  closed: {
    customer_deploy: false,
    stranger_host_execution: false,
    announcement: false,
    credential_use: false,
    money_movement: false,
    cli_reopen: false,
    python_byte_mutation: false,
    pe_confidential_copied: false,
  },
  files_sha256,
};

writeFileSync(join(ROOT, "BENCHMARK-MANIFEST.json"), `${JSON.stringify(manifest, null, 2)}\n`);
files_sha256["scripts/emit-pack.mjs"] = sha256("scripts/emit-pack.mjs");
manifest.files_sha256 = files_sha256;
writeFileSync(join(ROOT, "BENCHMARK-MANIFEST.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log("emitted", Object.keys(files_sha256).length, "hashes");
