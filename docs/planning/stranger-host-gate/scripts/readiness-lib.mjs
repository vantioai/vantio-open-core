import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PACKET_DIR = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(PACKET_DIR, "..", "..", "..");
const PACKET_PREFIX = "docs/planning/stranger-host-gate/";

export const CLASSIFICATION = "STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL";
export const PACKET_CLASSIFICATION = "STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH";
export const EXECUTION_BLOCKED = "STRANGER_HOST_EXECUTION_BLOCKED_READINESS_ONLY";
export const PREPARED_SHA = "5064f32f1cdfcb840dfd100e2ce5c712d046550d";
export const CURRENCY_SHA = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";

export const CHECKLIST_FIELDS = {
  named_host: "{{NAMED_HOST}}",
  owner_operator: "{{OWNER_OPERATOR}}",
  distro: "{{DISTRO}}",
  kernel: "{{KERNEL}}",
  arch: "{{ARCH}}",
  container_runtime_profile: "{{CONTAINER_RUNTIME_PROFILE}}",
  confidentiality_boundary: "{{CONFIDENTIALITY_BOUNDARY}}",
  artifact_route: "{{ARTIFACT_ROUTE}}",
  maintenance_window: "{{MAINTENANCE_WINDOW}}",
  rollback_authority: "{{ROLLBACK_AUTHORITY}}",
  independent_verifier: "{{INDEPENDENT_VERIFIER}}",
  stop_conditions: "{{STOP_CONDITIONS}}",
  founder_execution_authorization: "{{FOUNDER_EXECUTION_AUTHORIZATION}}",
};

export const FAMILY_NEEDLES = {
  ingress: ["ingress"],
  egress: ["egress"],
  "host-authority": ["host-authority", "host_authority"],
  "sequential-authority": ["sequential-authority", "sequential_authority"],
  health: ["health"],
  "progressive-enforcement": ["progressive-enforcement", "progressive_enforcement"],
};

export const FAMILY_IDS = Object.keys(FAMILY_NEEDLES);

const SCAN_ROOTS = ["tests", ".github/workflows", "packages", "scripts"];

function fail(reason) {
  return { ok: false, reason };
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

function readText(root, rel) {
  return readFileSync(join(root, rel), "utf8");
}

function gitStdout(root, args) {
  const result = spawnSync("git", args, { cwd: root, encoding: "utf8" });
  return result;
}

function lines(stdout) {
  return stdout.split("\n").map((line) => line.trim()).filter((line) => line.length > 0).sort();
}

function walk(root, relDir, hits) {
  const abs = join(root, relDir);
  if (!existsSync(abs)) {
    return;
  }
  for (const entry of readdirSync(abs, { withFileTypes: true })) {
    if (entry.name === "node_modules") {
      continue;
    }
    const rel = `${relDir}/${entry.name}`.split("\\").join("/");
    if (entry.isDirectory()) {
      walk(root, rel, hits);
      continue;
    }
    const low = rel.toLowerCase();
    for (const id of FAMILY_IDS) {
      if (FAMILY_NEEDLES[id].some((needle) => low.includes(needle))) {
        hits[id].push(rel);
      }
    }
  }
}

function scanFamilyPaths(root) {
  const hits = {};
  for (const id of FAMILY_IDS) {
    hits[id] = [];
  }
  for (const scanRoot of SCAN_ROOTS) {
    walk(root, scanRoot, hits);
  }
  for (const id of FAMILY_IDS) {
    hits[id].sort();
  }
  return hits;
}

function runNode(root, rel) {
  return spawnSync(process.execPath, [join(root, rel)], {
    cwd: root,
    encoding: "utf8",
  });
}

export function executionRequested(argv = process.argv, env = process.env) {
  if (argv.includes("--execute")) {
    return true;
  }
  if (env.STRANGER_HOST_EXECUTE !== undefined) {
    return true;
  }
  if (env.STRANGER_HOST_HOST !== undefined) {
    return true;
  }
  return false;
}

export function executionAuthGaps(input) {
  const gaps = [];
  const fields = input.fields ?? {};
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    const value = fields[key];
    if (typeof value !== "string" || value.length === 0 || value === CHECKLIST_FIELDS[key] || value.includes("{{")) {
      gaps.push(`UNFILLED:${key}`);
    }
  }
  if (input.inPlaceCompletion !== false) {
    gaps.push("IN_PLACE_COMPLETION_FORBIDDEN");
  }
  if (input.refuseExit !== 0) {
    gaps.push("REFUSE_SCRIPT");
  }
  if (input.founderStatus !== "AUTHORIZED") {
    gaps.push("FOUNDER_EXECUTION_AUTHORIZATION");
  }
  if (input.customerHost !== "FORBIDDEN") {
    gaps.push("CUSTOMER_HOST");
  }
  if (input.credentials !== "NONE") {
    gaps.push("CREDENTIALS");
  }
  if (Array.isArray(input.evidenceTiers) && input.evidenceTiers.length > 0) {
    gaps.push("EVIDENCE_TIER");
  }
  if (input.copiedAuthorization !== true) {
    gaps.push("COPIED_AUTHORIZATION");
  }
  return gaps;
}

export function loadState(root = REPO_ROOT) {
  const checklist = JSON.parse(readText(root, `${PACKET_PREFIX}authorization/EXECUTION-AUTH-CHECKLIST.template.json`));
  const placeholders = JSON.parse(readText(root, `${PACKET_PREFIX}PLACEHOLDER-MATRIX.json`));
  const manifest = JSON.parse(readText(root, `${PACKET_PREFIX}PACKET-MANIFEST.json`));
  const ciDiff = gitStdout(root, ["diff", "--name-only", PREPARED_SHA, CURRENCY_SHA, "--", ".github/workflows/ci.yml"]);
  const addedTests = gitStdout(root, ["diff", "--name-only", "--diff-filter=A", PREPARED_SHA, CURRENCY_SHA, "--", "tests"]);
  const modifiedTests = gitStdout(root, ["diff", "--name-only", "--diff-filter=M", PREPARED_SHA, CURRENCY_SHA, "--", "tests"]);
  const addedWorkflows = gitStdout(root, ["diff", "--name-only", "--diff-filter=A", PREPARED_SHA, CURRENCY_SHA, "--", ".github/workflows"]);
  const preparedAncestor = gitStdout(root, ["merge-base", "--is-ancestor", PREPARED_SHA, "HEAD"]);
  const currencyAncestor = gitStdout(root, ["merge-base", "--is-ancestor", CURRENCY_SHA, "HEAD"]);
  const postCurrencyCi = gitStdout(root, ["diff", "--name-only", CURRENCY_SHA, "HEAD", "--", ".github/workflows/ci.yml"]);
  const postCurrencyTests = gitStdout(root, ["diff", "--name-only", CURRENCY_SHA, "HEAD", "--", "tests"]);
  const postCurrencyWorkflows = gitStdout(root, ["diff", "--name-only", CURRENCY_SHA, "HEAD", "--", ".github/workflows"]);
  const refuseExecution = runNode(root, `${PACKET_PREFIX}scripts/refuse-stranger-host-execution.mjs`);
  const refuseRollback = runNode(root, `${PACKET_PREFIX}scripts/refuse-rollback.mjs`);
  const packetPrep = runNode(root, `${PACKET_PREFIX}scripts/verify-packet-prep.mjs`);
  return {
    checklist,
    placeholders,
    manifest,
    ciText: readText(root, ".github/workflows/ci.yml"),
    ciDiffStatus: ciDiff.status,
    ciDiffNames: lines(ciDiff.stdout ?? ""),
    addedTestsStatus: addedTests.status,
    addedTests: lines(addedTests.stdout ?? ""),
    modifiedTestsStatus: modifiedTests.status,
    modifiedTests: lines(modifiedTests.stdout ?? ""),
    addedWorkflowsStatus: addedWorkflows.status,
    addedWorkflows: lines(addedWorkflows.stdout ?? ""),
    preparedAncestor: preparedAncestor.status === 0,
    currencyAncestor: currencyAncestor.status === 0,
    postCurrencyCiStatus: postCurrencyCi.status,
    postCurrencyCi: lines(postCurrencyCi.stdout ?? ""),
    postCurrencyTestsStatus: postCurrencyTests.status,
    postCurrencyTests: lines(postCurrencyTests.stdout ?? ""),
    postCurrencyWorkflowsStatus: postCurrencyWorkflows.status,
    postCurrencyWorkflows: lines(postCurrencyWorkflows.stdout ?? ""),
    familyHits: scanFamilyPaths(root),
    refuseExecution: {
      status: refuseExecution.status,
      stdout: refuseExecution.stdout,
      stderr: refuseExecution.stderr,
    },
    refuseRollback: {
      status: refuseRollback.status,
      stdout: refuseRollback.stdout,
      stderr: refuseRollback.stderr,
    },
    packetPrep: {
      status: packetPrep.status,
      stdout: packetPrep.stdout,
      stderr: packetPrep.stderr,
    },
    texts: {
      readiness: readText(root, `${PACKET_PREFIX}07-READINESS-UPDATE.md`),
      placeholderMd: readText(root, `${PACKET_PREFIX}08-PLACEHOLDER-MATRIX.md`),
      checklistMd: readText(root, `${PACKET_PREFIX}09-EXECUTION-AUTH-CHECKLIST.md`),
      council: readText(root, `${PACKET_PREFIX}10-INDEPENDENT-COUNCIL.md`),
      boundary: readText(root, `${PACKET_PREFIX}00-PACKET-BOUNDARY.md`),
      runbook: readText(root, `${PACKET_PREFIX}05-RUNBOOK.md`),
      readme: readText(root, `${PACKET_PREFIX}README.md`),
      stops: readText(root, `${PACKET_PREFIX}03-STOP-CONDITIONS.md`),
      packetChecklist: readText(root, `${PACKET_PREFIX}01-PACKET-CHECKLIST.md`),
    },
    executionRequested: false,
  };
}

function requireMarker(text, marker, label) {
  if (!text.includes(marker)) {
    return fail(`${label} missing ${marker}`);
  }
  return null;
}

export function assess(state) {
  if (state.executionRequested === true) {
    return fail("execution requested");
  }
  if (state.preparedAncestor !== true) {
    return fail("prepared SHA is not an ancestor of HEAD");
  }
  if (state.currencyAncestor !== true) {
    return fail("currency SHA is not an ancestor of HEAD");
  }
  if (state.ciDiffStatus !== 0 || state.ciDiffNames.length !== 0) {
    return fail("ci.yml drift");
  }
  if (state.postCurrencyCiStatus !== 0 || state.postCurrencyCi.length !== 0) {
    return fail("ci.yml drift after currency SHA");
  }
  if (state.postCurrencyTestsStatus !== 0 || state.postCurrencyTests.length !== 0) {
    return fail("tests drift after currency SHA");
  }
  if (state.postCurrencyWorkflowsStatus !== 0 || state.postCurrencyWorkflows.length !== 0) {
    return fail("workflows drift after currency SHA");
  }
  if (!state.texts.readiness.includes("ci.yml is unchanged from the prepared SHA")) {
    return fail("readiness inventory missing ci statement");
  }
  if (state.addedTestsStatus !== 0 || state.modifiedTestsStatus !== 0 || state.addedWorkflowsStatus !== 0) {
    return fail("currency diff failed");
  }
  if (!sameList(state.addedTests, state.placeholders.tests_added_since_prepared_sha)) {
    return fail("added tests drift");
  }
  if (!sameList(state.modifiedTests, state.placeholders.tests_modified_since_prepared_sha)) {
    return fail("modified tests drift");
  }
  if (!sameList(state.addedWorkflows, state.placeholders.workflows_added_since_prepared_sha)) {
    return fail("added workflows drift");
  }

  const update = state.manifest.readiness_update;
  if (!update) {
    return fail("manifest readiness_update");
  }
  if (state.manifest.classification !== PACKET_CLASSIFICATION) {
    return fail("manifest prep classification");
  }
  if (state.manifest.execution_status !== "NOT_AUTHORIZED") {
    return fail("manifest execution_status");
  }
  if (state.manifest.mode !== "PREP_ONLY") {
    return fail("manifest mode");
  }
  if (!Array.isArray(state.manifest.evidence_tiers_assigned) || state.manifest.evidence_tiers_assigned.length !== 0) {
    return fail("manifest evidence tiers");
  }
  if (update.classification !== CLASSIFICATION) {
    return fail("readiness classification");
  }
  if (update.council_status !== "PENDING_INDEPENDENT_COUNCIL") {
    return fail("readiness council_status");
  }
  if (update.execution_status !== "NOT_AUTHORIZED") {
    return fail("readiness execution_status");
  }
  if (update.mode !== "READINESS_UPDATE_ONLY") {
    return fail("readiness mode");
  }
  if (update.force !== "WAVE2-TRACK-16") {
    return fail("readiness force");
  }
  if (update.currency_main_sha !== CURRENCY_SHA) {
    return fail("readiness currency sha");
  }
  if (update.ci_yml_changed_since_prepared_sha !== false) {
    return fail("readiness ci flag");
  }
  if (update.execution_auth_checklist !== "UNFILLED") {
    return fail("readiness checklist status");
  }
  if (update.placeholder_execution !== "NOT_EXECUTED") {
    return fail("readiness placeholder execution");
  }
  if (!Array.isArray(update.evidence_tiers_assigned) || update.evidence_tiers_assigned.length !== 0) {
    return fail("readiness evidence tiers");
  }

  if (!Array.isArray(state.manifest.later_commands)) {
    return fail("later_commands");
  }
  for (const command of state.manifest.later_commands) {
    for (const id of FAMILY_IDS) {
      if (command.toLowerCase().includes(id)) {
        return fail(`later_commands includes ${id}`);
      }
    }
  }
  for (const id of FAMILY_IDS) {
    if (state.ciText.toLowerCase().includes(id)) {
      return fail(`ci.yml includes ${id}`);
    }
  }

  const checklist = state.checklist;
  if (checklist.schema !== "vantio.stranger-host-gate.execution-auth-checklist/v1") {
    return fail("checklist schema");
  }
  if (checklist.force !== "WAVE2-TRACK-16") {
    return fail("checklist force");
  }
  if (checklist.status !== "UNFILLED") {
    return fail("checklist status");
  }
  if (checklist.execution_status !== "NOT_AUTHORIZED") {
    return fail("checklist execution_status");
  }
  if (checklist.mode !== "READINESS_UPDATE_ONLY") {
    return fail("checklist mode");
  }
  if (checklist.audience !== "INTERNAL_RESTRICTED") {
    return fail("checklist audience");
  }
  if (checklist.repository !== "vantioai/vantio-open-core") {
    return fail("checklist repository");
  }
  if (checklist.currency_main_sha !== CURRENCY_SHA || checklist.prepared_against_main_sha !== PREPARED_SHA) {
    return fail("checklist sha");
  }
  if (checklist.customer_host !== "FORBIDDEN") {
    return fail("checklist customer_host");
  }
  if (checklist.credentials !== "NONE") {
    return fail("checklist credentials");
  }
  if (checklist.in_place_completion !== "FORBIDDEN") {
    return fail("checklist in_place_completion");
  }
  if (checklist.copied_authorization !== false) {
    return fail("checklist copied_authorization");
  }
  if (checklist.assigns_evidence_tier !== false || checklist.assigns_stranger_host_proved !== false) {
    return fail("checklist evidence flags");
  }
  for (const [key, placeholder] of Object.entries(CHECKLIST_FIELDS)) {
    if (!checklist.fields || checklist.fields[key] !== placeholder) {
      return fail(`checklist field ${key}`);
    }
  }

  const gaps = executionAuthGaps({
    fields: checklist.fields,
    inPlaceCompletion: true,
    refuseExit: state.refuseExecution.status,
    founderStatus: "NOT_AUTHORIZED",
    customerHost: checklist.customer_host,
    credentials: checklist.credentials,
    evidenceTiers: [],
    copiedAuthorization: false,
  });
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    if (!gaps.includes(`UNFILLED:${key}`)) {
      return fail(`gap missing ${key}`);
    }
  }
  for (const gap of ["IN_PLACE_COMPLETION_FORBIDDEN", "REFUSE_SCRIPT", "FOUNDER_EXECUTION_AUTHORIZATION", "COPIED_AUTHORIZATION"]) {
    if (!gaps.includes(gap)) {
      return fail(`gap missing ${gap}`);
    }
  }

  if (state.refuseExecution.status !== 2 || state.refuseExecution.stdout !== "STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH\n" || state.refuseExecution.stderr) {
    return fail("refuse execution");
  }
  if (state.refuseRollback.status !== 2 || state.refuseRollback.stdout !== "STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH\n" || state.refuseRollback.stderr) {
    return fail("refuse rollback");
  }
  if (state.packetPrep.status !== 0 || state.packetPrep.stdout !== `${PACKET_CLASSIFICATION}\n` || state.packetPrep.stderr) {
    return fail("packet prep");
  }

  if (state.placeholders.execution !== "NOT_EXECUTED" || state.placeholders.evidence_tier !== "UNSET" || state.placeholders.in_later_commands !== false) {
    return fail("placeholder header");
  }
  if (state.placeholders.currency_main_sha !== CURRENCY_SHA || state.placeholders.prepared_against_main_sha !== PREPARED_SHA) {
    return fail("placeholder sha");
  }
  if (!Array.isArray(state.placeholders.families) || state.placeholders.families.length !== FAMILY_IDS.length) {
    return fail("placeholder family count");
  }
  for (let index = 0; index < FAMILY_IDS.length; index += 1) {
    const family = state.placeholders.families[index];
    const id = FAMILY_IDS[index];
    if (!family || family.id !== id) {
      return fail(`placeholder id ${id}`);
    }
    if (family.status !== "NOT_EXECUTED" || family.in_ci_yml !== false || family.in_later_commands !== false || family.evidence_tier !== "UNSET") {
      return fail(`placeholder row ${id}`);
    }
    const hits = state.familyHits[id] ?? [];
    const recorded = [...(family.repository_test_paths ?? [])].sort();
    if (!sameList(hits, recorded)) {
      return fail(`placeholder scan drift ${id}`);
    }
    const expectedSuite = recorded.length === 0 ? "ABSENT" : "NOT_THIS_GATE";
    if (family.named_suite !== expectedSuite) {
      return fail(`placeholder suite ${id}`);
    }
    const markerMiss = requireMarker(state.texts.placeholderMd, id, "placeholder md");
    if (markerMiss) {
      return markerMiss;
    }
    if (family.heading && !state.texts.placeholderMd.includes(family.heading)) {
      return fail(`placeholder heading ${id}`);
    }
    for (const path of recorded) {
      if (!state.texts.placeholderMd.includes(path) || !state.texts.readiness.includes(path)) {
        return fail(`placeholder path ${path}`);
      }
    }
  }
  if (!state.texts.placeholderMd.includes("NOT_EXECUTED") || !state.texts.placeholderMd.includes("ABSENT") || !state.texts.placeholderMd.includes("NOT_THIS_GATE")) {
    return fail("placeholder md status");
  }

  for (const path of state.placeholders.tests_added_since_prepared_sha) {
    const markerMiss = requireMarker(state.texts.readiness, path, "readiness");
    if (markerMiss) {
      return markerMiss;
    }
  }

  const readinessMarkers = [
    CLASSIFICATION,
    PACKET_CLASSIFICATION,
    "NOT_AUTHORIZED",
    "PENDING_INDEPENDENT_COUNCIL",
    CURRENCY_SHA,
    PREPARED_SHA,
    "bc-ad6e7ae1-4de4-5416-bc9d-a6971c7717f4",
    "SH-STOP-21",
    "READINESS_UPDATE_ONLY",
  ];
  for (const marker of readinessMarkers) {
    const markerMiss = requireMarker(state.texts.readiness, marker, "readiness");
    if (markerMiss) {
      return markerMiss;
    }
  }
  for (const placeholder of Object.values(CHECKLIST_FIELDS)) {
    const markerMiss = requireMarker(state.texts.readiness, placeholder, "readiness");
    if (markerMiss) {
      return markerMiss;
    }
    const checklistMiss = requireMarker(state.texts.checklistMd, placeholder, "checklist md");
    if (checklistMiss) {
      return checklistMiss;
    }
  }
  for (const marker of ["UNFILLED", "NOT_AUTHORIZED", "FORBIDDEN", "executionAuthGaps"]) {
    const markerMiss = requireMarker(state.texts.checklistMd, marker, "checklist md");
    if (markerMiss) {
      return markerMiss;
    }
  }
  if (state.texts.council.includes("COUNCIL_PASSED")) {
    return fail("council records a pass");
  }
  for (const marker of ["PENDING_INDEPENDENT_COUNCIL", "UNSAT", CLASSIFICATION, "NOT_AUTHORIZED"]) {
    const markerMiss = requireMarker(state.texts.council, marker, "council");
    if (markerMiss) {
      return markerMiss;
    }
  }
  for (const marker of [CLASSIFICATION, CURRENCY_SHA, "READINESS_UPDATE_ONLY"]) {
    const markerMiss = requireMarker(state.texts.boundary, marker, "boundary");
    if (markerMiss) {
      return markerMiss;
    }
  }
  for (const marker of ["verify-readiness-update.mjs", EXECUTION_BLOCKED, "Phase 0b"]) {
    const markerMiss = requireMarker(state.texts.runbook, marker, "runbook");
    if (markerMiss) {
      return markerMiss;
    }
  }
  for (const marker of [CLASSIFICATION, PACKET_CLASSIFICATION, "verify-readiness-update.mjs", "verify-packet-prep.mjs"]) {
    const markerMiss = requireMarker(state.texts.readme, marker, "readme");
    if (markerMiss) {
      return markerMiss;
    }
  }
  if (!state.texts.stops.includes("SH-STOP-21")) {
    return fail("stops missing SH-STOP-21");
  }
  for (const marker of ["P13", "L10", CLASSIFICATION]) {
    const markerMiss = requireMarker(state.texts.packetChecklist, marker, "packet checklist");
    if (markerMiss) {
      return markerMiss;
    }
  }
  return { ok: true, classification: CLASSIFICATION };
}

export function runCli(argv = process.argv, env = process.env) {
  if (executionRequested(argv, env)) {
    process.stdout.write(`${EXECUTION_BLOCKED}\n`);
    process.exit(2);
  }
  const state = loadState(REPO_ROOT);
  const result = assess(state);
  if (!result.ok) {
    process.stdout.write(`STRANGER_HOST_READINESS_BLOCKED ${result.reason}\n`);
    process.exit(1);
  }
  process.stdout.write(`${result.classification}\n`);
}
