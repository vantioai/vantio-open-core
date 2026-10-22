/**
 * Re-check the lane seal digest against the tree on disk.
 *
 * This does not build the private engine and does not move a seal constant.
 * formal_reproducibility stays NOT_CLAIMED.
 */

import { createHash } from "node:crypto";
import { createReadStream, existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";
import { laneSeal, publicPin as readPublicPin, readSealHistory } from "./pe_canonical_seal.mjs";

const SKIP = new Set([".git", "node_modules", "__pycache__", ".venv", "dist"]);
const MANIFEST_FILES = [
  ".github/workflows/enterprise-slsa-provenance.yml",
  "deploy/docker/Dockerfile.observe",
  "packages/vantio-install/vantio_install/constants.py",
  "scripts/gap/t1-stranger-host/constants.py",
  "scripts/release/seal-identity-recheck.mjs",
  "release/pe-canonical-seal.json",
];

export async function recheck(root) {
  const stranger = readFileSync(join(root, "scripts/gap/t1-stranger-host/constants.py"), "utf8");
  const working = laneSeal(root);
  const previous = readSealHistory(root).previous_working_seal;
  const publicPin = readPublicPin(root);
  const lanePrefix = working.slice(0, 8);
  const files = await walk(root);
  const matched = files.filter((row) => row.sha256 === working).map((row) => row.path);
  const engineDockerfile = files.some((row) => {
    if (!row.path.includes("Dockerfile")) return false;
    const text = readFileSync(join(root, row.path), "utf8");
    return text.includes("vantio-loader") || text.includes("bpf-linker");
  });
  const manifest = await manifestText(root);
  const manifestAgain = await manifestText(root);
  const agree = manifest === manifestAgain;
  return {
    bytes_matching_digest: matched,
    cargo_toml_present: existsSync(join(root, "Cargo.toml")),
    comparison_aliases_working: /^COMPARISON_SEAL\s*=\s*WORKING_SEAL$/m.test(stranger),
    constants_moved: false,
    digest_role_on_main: "WORKING_SEAL",
    digest_under_recheck: working,
    previous_working_seal: previous,
    engine_dockerfile_present: engineDockerfile,
    engine_seal_label: "Lab-only",
    engine_seal_rebuilt: false,
    formal_reproducibility: "NOT_CLAIMED",
    lane_prefix: lanePrefix,
    observe_dockerfile_present: existsSync(join(root, "deploy/docker/Dockerfile.observe")),
    open_core_manifest_label: agree ? "Verified" : "Lab-only",
    open_core_manifest_passes_agree: agree,
    open_core_manifest_sha256: sha256Text(manifest),
    public_installer_pin: publicPin,
    seal_oci_tar_present: files.some((row) => row.path.endsWith("seal.oci.tar")),
    working_seal_constant: working,
  };
}

export function assertShape(body) {
  const errors = [];
  if (!body.digest_under_recheck.startsWith(body.lane_prefix)) errors.push("prefix");
  if (body.digest_under_recheck !== body.working_seal_constant) errors.push("not_the_working_seal");
  if (!body.previous_working_seal.startsWith("bbb1025d")) errors.push("previous_prefix");
  if (body.previous_working_seal === body.working_seal_constant) errors.push("previous_is_current");
  if (body.digest_under_recheck === body.public_installer_pin) errors.push("working_is_public_pin");
  if (!body.comparison_aliases_working) errors.push("comparison_alias");
  if (body.bytes_matching_digest.length !== 0) errors.push("bytes_present");
  if (body.seal_oci_tar_present) errors.push("oci_present");
  if (body.cargo_toml_present) errors.push("cargo_present");
  if (body.engine_seal_rebuilt) errors.push("rebuilt");
  if (body.formal_reproducibility !== "NOT_CLAIMED") errors.push("formal");
  if (!body.open_core_manifest_passes_agree) errors.push("manifest");
  if (body.open_core_manifest_sha256 === body.digest_under_recheck) errors.push("manifest_is_seal");
  if (body.engine_seal_label !== "Lab-only") errors.push("engine_label");
  if (body.open_core_manifest_label !== "Verified") errors.push("manifest_label");
  if (body.engine_dockerfile_present) errors.push("engine_docker");
  if (!body.observe_dockerfile_present) errors.push("observe_docker");
  if (!body.digest_under_recheck.startsWith(body.lane_prefix)) errors.push("lane_prefix");
  return errors;
}

function sha256Text(text) {
  return createHash("sha256").update(text).digest("hex");
}

async function manifestText(root) {
  const lines = [];
  for (const rel of MANIFEST_FILES) {
    lines.push(`${await hashFile(join(root, rel))}  ${rel}`);
  }
  return `${lines.join("\n")}\n`;
}

async function walk(root) {
  const rows = [];
  for (const path of listFiles(root)) {
    const rel = relative(root, path).split("\\").join("/");
    rows.push({ path: rel, sha256: await hashFile(path) });
  }
  rows.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  return rows;
}

function listFiles(dir) {
  const found = [];
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const path = join(dir, name);
    let info;
    try {
      info = statSync(path);
    } catch {
      continue;
    }
    if (info.isDirectory()) found.push(...listFiles(path));
    else if (info.isFile()) found.push(path);
  }
  return found;
}

function hashFile(path) {
  return new Promise((resolve, reject) => {
    const hash = createHash("sha256");
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
    stream.on("error", reject);
  });
}

async function main() {
  const root = process.argv[2] || join(import.meta.dirname, "..", "..");
  const body = await recheck(root);
  const errors = assertShape(body);
  if (errors.length) {
    process.stderr.write(`${errors.join(",")}\n`);
    process.exitCode = 1;
  }
  const out = join(root, "docs/planning/seal-identity-recheck/RESULT.json");
  writeFileSync(out, `${JSON.stringify(body, null, 2)}\n`);
  process.stdout.write(`${body.open_core_manifest_sha256}\n`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
