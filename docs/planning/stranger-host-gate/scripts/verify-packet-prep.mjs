import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PACKET_DIR = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(PACKET_DIR, "..", "..", "..");
const PACKET_PREFIX = "docs/planning/stranger-host-gate/";
const MANIFEST_REL = `${PACKET_PREFIX}PACKET-MANIFEST.json`;

const CLASSIFICATION = "STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH";
const PREPARED_AGAINST = "5064f32f1cdfcb840dfd100e2ce5c712d046550d";

const REQUIRED = [
  `${PACKET_PREFIX}README.md`,
  `${PACKET_PREFIX}00-PACKET-BOUNDARY.md`,
  `${PACKET_PREFIX}01-PACKET-CHECKLIST.md`,
  `${PACKET_PREFIX}02-EVIDENCE-REQUIREMENTS.md`,
  `${PACKET_PREFIX}03-STOP-CONDITIONS.md`,
  `${PACKET_PREFIX}04-FOUNDER-AUTHORIZATION-TEMPLATE.md`,
  `${PACKET_PREFIX}05-RUNBOOK.md`,
  `${PACKET_PREFIX}06-ROLLBACK.md`,
  MANIFEST_REL,
  `${PACKET_PREFIX}authorization/FOUNDER-AUTHORIZATION.template.json`,
  `${PACKET_PREFIX}07-READINESS-UPDATE.md`,
  `${PACKET_PREFIX}08-PLACEHOLDER-MATRIX.md`,
  `${PACKET_PREFIX}09-EXECUTION-AUTH-CHECKLIST.md`,
  `${PACKET_PREFIX}10-INDEPENDENT-COUNCIL.md`,
  `${PACKET_PREFIX}PLACEHOLDER-MATRIX.json`,
  `${PACKET_PREFIX}authorization/EXECUTION-AUTH-CHECKLIST.template.json`,
  `${PACKET_PREFIX}scripts/verify-packet-prep.mjs`,
  `${PACKET_PREFIX}scripts/refuse-stranger-host-execution.mjs`,
  `${PACKET_PREFIX}scripts/refuse-rollback.mjs`,
  `${PACKET_PREFIX}scripts/readiness-lib.mjs`,
  `${PACKET_PREFIX}scripts/verify-readiness-update.mjs`,
  `${PACKET_PREFIX}scripts/readiness.test.mjs`,
];

const LATER_COMMANDS = [
  "pnpm install --frozen-lockfile",
  "pnpm --filter @vantio/cli run lint",
  "pnpm --filter @vantio/agent-sdk run typecheck",
  "pnpm --filter @vantio/agent-sdk run typecheck:test",
  "pnpm --filter @vantio/cli run test",
  "pnpm --filter @vantio/agent-sdk run test",
  "pnpm --filter @vantio/agent-sdk run build",
  "python -m pip install --disable-pip-version-check requests httpx aiohttp urllib3",
  "python -m unittest discover -s tests -t . -v",
  "python3 -m pip install --disable-pip-version-check 'pyyaml==6.0.1'",
  "node --test scripts/release/governance.test.mjs",
  "python3 scripts/release/test_promote_pypi.py -v",
  "python3 scripts/release/test_pypi_publish_workflow.py -v",
  "pnpm install --frozen-lockfile",
  'mkdir -p "$RUNNER_TEMP/candidates"',
  'npm pack --ignore-scripts --pack-destination "$RUNNER_TEMP/candidates"',
  'mkdir -p "$RUNNER_TEMP/candidates-py"',
  "python3 -m pip install --disable-pip-version-check build",
  'python3 -m build --outdir "$RUNNER_TEMP/candidates-py" packages/vantio-agent-sdk-py',
];

const PUBLISHED_COMMANDS = [
  "npm install -g @vantio/cli@0.3.24",
  "vantio --version",
  "vantio status",
  "pip install 'vantio-agent-sdk==3.0.14'",
  "python -c 'import vantio; print(vantio.__version__)'",
];

const REFUSE_DENYLIST = [
  "child_process",
  "node:net",
  "node:http",
  "node:https",
  "node:fs",
  "ssh-keygen",
  "unlink",
  "rmSync",
  "rmdir",
  "spawn",
  "exec(",
  "execSync",
  "fetch(",
  "process.exit(0)",
];

function marker(parts) {
  return parts.join("");
}

const SECRET_MARKERS = [
  marker(["BEGIN ", "OPENSSH ", "PRIVATE ", "KEY"]),
  marker(["BEGIN ", "RSA ", "PRIVATE ", "KEY"]),
  marker(["BEGIN ", "PRIVATE ", "KEY"]),
  marker(["ghp", "_"]),
  marker(["github", "_pat_"]),
  marker(["sk", "_live_"]),
  marker(["npm", "_"]),
  marker(["AKI", "A"]),
];

const AUTH_FIELDS = {
  schema: "vantio.stranger-host-gate.authorization/v1",
  force: "WS3-P34",
  status: "NOT_AUTHORIZED",
  mode: "PREP_ONLY",
  audience: "INTERNAL_RESTRICTED",
  repository: "vantioai/vantio-open-core",
  locked_main_sha: "{{FOUNDER_LOCKED_MAIN_SHA}}",
  host_class: "{{FOUNDER_NAMED_HOST_CLASS}}",
  host_owner: "{{FOUNDER_NAMED_HOST_OWNER}}",
  customer_host: "FORBIDDEN",
  credentials: "NONE",
  published_install_smoke: "NO",
  source_tree_ci_parity: "UNFILLED",
  assigns_evidence_tier: false,
  assigns_stranger_host_proved: false,
  gate_8: "CLOSED",
};

function fail(reason) {
  process.stdout.write(`STRANGER_HOST_PACKET_BLOCKED ${reason}\n`);
  process.exit(1);
}

function executionBlocked(reason) {
  process.stdout.write(`STRANGER_HOST_EXECUTION_BLOCKED_PREP_ONLY ${reason}\n`);
  process.exit(2);
}

function git(args) {
  const result = spawnSync("git", args, { cwd: REPO_ROOT, encoding: "utf8" });
  if (result.error) {
    fail(`git ${args[0]} failed to start`);
  }
  return result;
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function listPacketFiles(dir) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isSymbolicLink()) {
      fail(`symlink ${relative(REPO_ROOT, full)}`);
    }
    if (entry.isDirectory()) {
      found.push(...listPacketFiles(full));
      continue;
    }
    if (!entry.isFile()) {
      fail(`unexpected entry ${relative(REPO_ROOT, full)}`);
    }
    found.push(relative(REPO_ROOT, full).split("\\").join("/"));
  }
  return found;
}

function sameList(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return false;
    }
  }
  return true;
}

function assertRefuses(rel, token) {
  const source = readFileSync(join(REPO_ROOT, rel), "utf8");
  if (!source.includes(token)) {
    fail(`${rel} missing refusal token`);
  }
  if (!source.includes("process.exit(2)")) {
    fail(`${rel} missing exit 2`);
  }
  if (/^\s*import\s/m.test(source)) {
    fail(`${rel} imports a module`);
  }
  for (const needle of REFUSE_DENYLIST) {
    if (source.includes(needle)) {
      fail(`${rel} contains ${needle}`);
    }
  }
  const run = spawnSync(process.execPath, [join(REPO_ROOT, rel)], { encoding: "utf8" });
  if (run.status !== 2) {
    fail(`${rel} exited ${String(run.status)}`);
  }
  if (run.stdout !== `${token}\n`) {
    fail(`${rel} stdout mismatch`);
  }
  if (run.stderr) {
    fail(`${rel} wrote stderr`);
  }
}

if (process.argv.includes("--execute")) {
  executionBlocked("--execute");
}
if (process.env.STRANGER_HOST_EXECUTE !== undefined || process.env.STRANGER_HOST_HOST !== undefined) {
  executionBlocked("execution environment is set");
}
if (!existsSync(join(REPO_ROOT, "package.json"))) {
  fail("repository root was not resolved");
}

const ancestor = git(["merge-base", "--is-ancestor", PREPARED_AGAINST, "HEAD"]);
if (ancestor.status !== 0) {
  fail(`prepared SHA ${PREPARED_AGAINST} is not an ancestor of HEAD`);
}

const dirty = []
  .concat(git(["diff", "--name-only", "-z", "HEAD"]).stdout.split("\0"))
  .concat(git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout.split("\0"))
  .filter((path) => path.length > 0);
for (const path of dirty) {
  if (!path.startsWith(PACKET_PREFIX)) {
    fail(`path outside the packet: ${path}`);
  }
}

const present = listPacketFiles(PACKET_DIR).sort();
const required = [...REQUIRED].sort();
if (!sameList(present, required)) {
  fail(`packet file set mismatch: ${present.join(",")}`);
}

const manifestBytes = readFileSync(join(REPO_ROOT, MANIFEST_REL));
const manifest = JSON.parse(manifestBytes.toString("utf8"));
if (manifest.classification !== CLASSIFICATION) {
  fail("manifest classification");
}
if (manifest.execution_status !== "NOT_AUTHORIZED") {
  fail("manifest execution_status");
}
if (manifest.mode !== "PREP_ONLY") {
  fail("manifest mode");
}
if (manifest.audience !== "INTERNAL_RESTRICTED") {
  fail("manifest audience");
}
if (manifest.force !== "WS3-P34") {
  fail("manifest force");
}
if (manifest.repository !== "vantioai/vantio-open-core") {
  fail("manifest repository");
}
if (manifest.prepared_against_main_sha !== PREPARED_AGAINST) {
  fail("manifest prepared SHA");
}
if (!Array.isArray(manifest.evidence_tiers_assigned) || manifest.evidence_tiers_assigned.length !== 0) {
  fail("manifest evidence tiers");
}
if (!sameList(manifest.later_commands, LATER_COMMANDS)) {
  fail("manifest later_commands");
}
if (!sameList(manifest.published_commands_default_off, PUBLISHED_COMMANDS)) {
  fail("manifest published commands");
}

const hashed = new Map();
for (const entry of manifest.files) {
  if (hashed.has(entry.path)) {
    fail(`duplicate manifest path ${entry.path}`);
  }
  hashed.set(entry.path, entry.sha256);
}
const expectedHashed = REQUIRED.filter((path) => path !== MANIFEST_REL).sort();
const listed = [...hashed.keys()].sort();
if (!sameList(listed, expectedHashed)) {
  fail("manifest file list");
}
for (const path of expectedHashed) {
  const bytes = readFileSync(join(REPO_ROOT, path));
  if (sha256(bytes) !== hashed.get(path)) {
    fail(`hash mismatch ${path}`);
  }
}

const boundary = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}00-PACKET-BOUNDARY.md`), "utf8");
for (const marker of [CLASSIFICATION, "PREP_ONLY", "INTERNAL_RESTRICTED", PREPARED_AGAINST, "bc-22d4d08f-d82d-5241-82ee-1a238b4c3e3f"]) {
  if (!boundary.includes(marker)) {
    fail(`boundary missing ${marker}`);
  }
}

const checklist = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}01-PACKET-CHECKLIST.md`), "utf8");
for (const marker of [CLASSIFICATION, "P1", "P12", "L1", "LATER"]) {
  if (!checklist.includes(marker)) {
    fail(`checklist missing ${marker}`);
  }
}

const evidence = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}02-EVIDENCE-REQUIREMENTS.md`), "utf8");
for (const marker of ["UNSET", "STRANGER_HOST_PROVED", "PROVED_EXTERNAL", "CUSTOMER_VALIDATED", ".github/workflows/ci.yml"]) {
  if (!evidence.includes(marker)) {
    fail(`evidence requirements missing ${marker}`);
  }
}

const stops = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}03-STOP-CONDITIONS.md`), "utf8");
for (let index = 1; index <= 20; index += 1) {
  const id = `SH-STOP-${String(index).padStart(2, "0")}`;
  if (!stops.includes(id)) {
    fail(`stop conditions missing ${id}`);
  }
}
if (!stops.includes("SH-STOP-21")) {
  fail("stop conditions missing SH-STOP-21");
}

const template = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}04-FOUNDER-AUTHORIZATION-TEMPLATE.md`), "utf8");
for (const marker of ["NOT AUTHORIZED", "{{FOUNDER_LOCKED_MAIN_SHA}}", "{{FOUNDER_NAMED_HOST_CLASS}}", "{{FOUNDER_NAMED_HOST_OWNER}}"]) {
  if (!template.includes(marker)) {
    fail(`authorization template missing ${marker}`);
  }
}

const runbook = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}05-RUNBOOK.md`), "utf8");
for (const marker of ["NOT AUTHORIZED", ".github/workflows/ci.yml", "packages/vantio-agent-sdk-py", "published_install_smoke", "Default: NO"]) {
  if (!runbook.includes(marker)) {
    fail(`runbook missing ${marker}`);
  }
}
for (const command of LATER_COMMANDS.concat(PUBLISHED_COMMANDS)) {
  if (!runbook.includes(command)) {
    fail(`runbook missing command ${command}`);
  }
}

const rollback = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}06-ROLLBACK.md`), "utf8");
for (const marker of ["NOT AUTHORIZED", "disposable", "SH-STOP-20", "pip uninstall vantio-agent-sdk"]) {
  if (!rollback.includes(marker)) {
    fail(`rollback missing ${marker}`);
  }
}
if (rollback.includes("pip uninstall -y")) {
  fail("rollback attributes pip uninstall -y to the manual");
}

const CI_STRACE_INSTALL = "sudo apt-get update && sudo apt-get install -y strace";
if (!runbook.includes(CI_STRACE_INSTALL)) {
  fail("runbook missing CI strace install citation");
}
if (!runbook.includes("Cited and absent from `later_commands`")) {
  fail("runbook missing later_commands omission citation");
}
if (LATER_COMMANDS.includes(CI_STRACE_INSTALL)) {
  fail("later_commands includes the OS package install");
}
const frozenInstalls = LATER_COMMANDS.filter((command) => command === "pnpm install --frozen-lockfile");
if (frozenInstalls.length !== 2) {
  fail("later_commands must cite both pnpm install steps");
}

const SHIELD_FILES = [
  "test_sdk.py",
  "test_http_observe.py",
  "test_optics_status.py",
  "test_socket_timing.py",
  "test_outcome_clarity.py",
  "test_telemetry.py",
  "send_run_telemetry_once",
  "MockServer",
];
const FALSE_SHIELD_CLAIM = "does not call `shield()`";
for (const rel of [
  `${PACKET_PREFIX}00-PACKET-BOUNDARY.md`,
  `${PACKET_PREFIX}03-STOP-CONDITIONS.md`,
  `${PACKET_PREFIX}04-FOUNDER-AUTHORIZATION-TEMPLATE.md`,
  `${PACKET_PREFIX}05-RUNBOOK.md`,
]) {
  const text = readFileSync(join(REPO_ROOT, rel), "utf8");
  if (text.includes(FALSE_SHIELD_CLAIM) || text.includes("The default matrix does not call")) {
    fail(`${rel} still denies shield() in the default matrix`);
  }
}
for (const marker of SHIELD_FILES) {
  if (!boundary.includes(marker) || !stops.includes(marker)) {
    fail(`shield() citation missing ${marker}`);
  }
}

const readme = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}README.md`), "utf8");
if (!readme.includes(CLASSIFICATION) || !readme.includes("verify-packet-prep.mjs")) {
  fail("readme missing entrypoint");
}

const authPath = `${PACKET_PREFIX}authorization/FOUNDER-AUTHORIZATION.template.json`;
const auth = JSON.parse(readFileSync(join(REPO_ROOT, authPath), "utf8"));
for (const [key, value] of Object.entries(AUTH_FIELDS)) {
  if (auth[key] !== value) {
    fail(`authorization field ${key}`);
  }
}
if (auth.execution_auth_checklist !== "UNFILLED") {
  fail("authorization execution_auth_checklist");
}
if (auth.in_place_checklist_completion !== "FORBIDDEN") {
  fail("authorization in_place_checklist_completion");
}

const readinessUpdate = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}07-READINESS-UPDATE.md`), "utf8");
for (const marker of [
  "STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL",
  "NOT_AUTHORIZED",
  "89f95099d0dce463307eb75d78e7fcf2ef99feb2",
  "PENDING_INDEPENDENT_COUNCIL",
]) {
  if (!readinessUpdate.includes(marker)) {
    fail(`readiness update missing ${marker}`);
  }
}
const checklistDoc = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}09-EXECUTION-AUTH-CHECKLIST.md`), "utf8");
for (const marker of [
  "{{NAMED_HOST}}",
  "{{OWNER_OPERATOR}}",
  "{{DISTRO}}",
  "{{KERNEL}}",
  "{{ARCH}}",
  "{{CONTAINER_RUNTIME_PROFILE}}",
  "{{CONFIDENTIALITY_BOUNDARY}}",
  "{{ARTIFACT_ROUTE}}",
  "{{MAINTENANCE_WINDOW}}",
  "{{ROLLBACK_AUTHORITY}}",
  "{{INDEPENDENT_VERIFIER}}",
  "{{STOP_CONDITIONS}}",
  "{{FOUNDER_EXECUTION_AUTHORIZATION}}",
  "UNFILLED",
]) {
  if (!checklistDoc.includes(marker)) {
    fail(`execution checklist missing ${marker}`);
  }
}
const placeholderDoc = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}08-PLACEHOLDER-MATRIX.md`), "utf8");
for (const marker of [
  "ingress",
  "egress",
  "host-authority",
  "sequential-authority",
  "health",
  "progressive-enforcement",
  "NOT_EXECUTED",
]) {
  if (!placeholderDoc.includes(marker)) {
    fail(`placeholder matrix missing ${marker}`);
  }
}
const councilDoc = readFileSync(join(REPO_ROOT, `${PACKET_PREFIX}10-INDEPENDENT-COUNCIL.md`), "utf8");
if (!councilDoc.includes("PENDING_INDEPENDENT_COUNCIL") || !councilDoc.includes("UNSAT")) {
  fail("council stub missing status");
}
if (councilDoc.includes("COUNCIL_PASSED")) {
  fail("council file records a pass");
}

for (const path of present) {
  const text = readFileSync(join(REPO_ROOT, path));
  const decoded = text.toString("utf8");
  for (const marker of SECRET_MARKERS) {
    if (decoded.includes(marker)) {
      fail(`secret marker in ${path}`);
    }
  }
}

assertRefuses(
  `${PACKET_PREFIX}scripts/refuse-stranger-host-execution.mjs`,
  "STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH",
);
assertRefuses(
  `${PACKET_PREFIX}scripts/refuse-rollback.mjs`,
  "STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH",
);

process.stdout.write(`${CLASSIFICATION}\n`);
