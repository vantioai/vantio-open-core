import { createHash } from "node:crypto";
import { chmodSync, readFileSync, writeFileSync } from "node:fs";

function fail(reason) {
  process.stderr.write(`clean-host: manifest rejected: ${reason}\n`);
  process.exit(27);
}

const [cycleId, commit, dirtyFlag, runPath, outPath, packageJsonPath] = process.argv.slice(2);
if (!cycleId || !commit || !dirtyFlag || !runPath || !outPath || !packageJsonPath) {
  fail("arguments are cycle, commit, dirty, run, out, package.json");
}
if (!/^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$/.test(cycleId)) fail("cycle id");
if (!/^[0-9a-f]{40}$/.test(commit)) fail("commit");
if (dirtyFlag !== "true" && dirtyFlag !== "false") fail("dirty flag");

const bytes = readFileSync(runPath);
const pkg = JSON.parse(readFileSync(packageJsonPath, "utf8"));
const manifest = {
  document: "CLEAN_HOST_CYCLE_MANIFEST",
  audience: "INTERNAL_RESTRICTED",
  schema_status: "unstable-pre-1.0",
  environment_class: "CLEAN_HOST_INTERNAL_PROOF",
  evidence_tier: "UNSET",
  stranger_host: "NOT_RUN",
  phantom_box: "EXCLUDED",
  customer_validation: "UNSET",
  independent_verifier: "UNSET",
  requirement_status_label: "INTERNAL_PROOF",
  requirement_status_note:
    "INTERNAL_PROOF names this lab class. It is not an evidence tier. It is not customer validation. This file does not update the traceability matrix.",
  product_seal: false,
  bookkeeping_sha256_is_a_seal: false,
  cli_package: pkg.name,
  cli_version: pkg.version,
  source_commit: commit,
  worktree_dirty: dirtyFlag === "true",
  cycle_id: cycleId,
  run_file: {
    name: runPath.split("/").pop(),
    byte_length: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  },
};

writeFileSync(outPath, `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o600 });
chmodSync(outPath, 0o600);
process.stdout.write("manifest\n");
