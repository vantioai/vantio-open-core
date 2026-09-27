import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  CHECKLIST_FIELDS,
  CLASSIFICATION,
  EXECUTION_BLOCKED,
  FAMILY_IDS,
  PACKET_CLASSIFICATION,
  assess,
  executionAuthGaps,
  loadState,
} from "./readiness-lib.mjs";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PACKET_DIR = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(PACKET_DIR, "..", "..", "..");
const READINESS_CLI = join(PACKET_DIR, "scripts", "verify-readiness-update.mjs");
const PREP_CLI = join(PACKET_DIR, "scripts", "verify-packet-prep.mjs");
const REFUSE_EXEC = join(PACKET_DIR, "scripts", "refuse-stranger-host-execution.mjs");
const REFUSE_ROLLBACK = join(PACKET_DIR, "scripts", "refuse-rollback.mjs");

function run(script, args = [], env = {}) {
  return spawnSync(process.execPath, [script, ...args], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    env: { ...process.env, ...env },
  });
}

function baseState() {
  const state = loadState(REPO_ROOT);
  return structuredClone(state);
}

test("readiness verifier prints the council handoff", () => {
  const result = run(READINESS_CLI);
  assert.equal(result.status, 0);
  assert.equal(result.stdout, `${CLASSIFICATION}\n`);
  assert.equal(result.stderr, "");
});

test("prep verifier still prints the prep classification", () => {
  const result = run(PREP_CLI);
  assert.equal(result.status, 0);
  assert.equal(result.stdout, `${PACKET_CLASSIFICATION}\n`);
  assert.equal(result.stderr, "");
});

test("execution entrypoint refuses", () => {
  const result = run(REFUSE_EXEC);
  assert.equal(result.status, 2);
  assert.equal(result.stdout, "STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH\n");
  assert.equal(result.stderr, "");
});

test("rollback entrypoint refuses", () => {
  const result = run(REFUSE_ROLLBACK);
  assert.equal(result.status, 2);
  assert.equal(result.stdout, "STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH\n");
  assert.equal(result.stderr, "");
});

test("readiness verifier refuses --execute", () => {
  const result = run(READINESS_CLI, ["--execute"]);
  assert.equal(result.status, 2);
  assert.equal(result.stdout, `${EXECUTION_BLOCKED}\n`);
  assert.equal(result.stderr, "");
});

test("readiness verifier refuses STRANGER_HOST_EXECUTE", () => {
  const result = run(READINESS_CLI, [], { STRANGER_HOST_EXECUTE: "1" });
  assert.equal(result.status, 2);
  assert.equal(result.stdout, `${EXECUTION_BLOCKED}\n`);
});

test("readiness verifier refuses STRANGER_HOST_HOST", () => {
  const result = run(READINESS_CLI, [], { STRANGER_HOST_HOST: "named.example" });
  assert.equal(result.status, 2);
  assert.equal(result.stdout, `${EXECUTION_BLOCKED}\n`);
});

test("intact packet state passes assess", () => {
  const result = assess(baseState());
  assert.equal(result.ok, true, result.reason);
  assert.equal(result.classification, CLASSIFICATION);
});

test("each checklist field rejects an in-place name", () => {
  const intact = baseState();
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    const state = structuredClone(intact);
    state.checklist.fields[key] = "filled-for-test";
    const result = assess(state);
    assert.equal(result.ok, false, key);
    assert.match(result.reason, new RegExp(key));
  }
});

test("each placeholder family rejects EXECUTED", () => {
  const intact = baseState();
  for (const id of FAMILY_IDS) {
    const state = structuredClone(intact);
    const family = state.placeholders.families.find((row) => row.id === id);
    family.status = "EXECUTED";
    const result = assess(state);
    assert.equal(result.ok, false, id);
    assert.match(result.reason, new RegExp(id));
  }
});

test("assigned evidence tiers fail assess", () => {
  const state = baseState();
  state.manifest.evidence_tiers_assigned = ["STRANGER_HOST_PROVED"];
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /evidence tiers/);
});

test("readiness execution_status AUTHORIZED fails assess", () => {
  const state = baseState();
  state.manifest.readiness_update.execution_status = "AUTHORIZED";
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /execution_status/);
});

test("a later_commands entry that names a placeholder family fails assess", () => {
  const state = baseState();
  state.manifest.later_commands = state.manifest.later_commands.concat(["run ingress suite"]);
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /ingress/);
});

test("council pass wording fails assess", () => {
  const state = baseState();
  state.texts.council += "\nCOUNCIL_PASSED\n";
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /council records a pass/);
});

test("health scan drift fails assess", () => {
  const state = baseState();
  state.placeholders.families.find((row) => row.id === "health").repository_test_paths = [];
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /health/);
});

test("ci.yml drift after the currency SHA fails assess", () => {
  const state = baseState();
  state.postCurrencyCi = [".github/workflows/ci.yml"];
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /after currency SHA/);
});

test("execution requested fails assess", () => {
  const state = baseState();
  state.executionRequested = true;
  const result = assess(state);
  assert.equal(result.ok, false);
  assert.match(result.reason, /execution requested/);
});

test("in-packet checklist keeps every authorization gap", () => {
  const state = baseState();
  const gaps = executionAuthGaps({
    fields: state.checklist.fields,
    inPlaceCompletion: true,
    refuseExit: state.refuseExecution.status,
    founderStatus: "NOT_AUTHORIZED",
    customerHost: "FORBIDDEN",
    credentials: "NONE",
    evidenceTiers: [],
    copiedAuthorization: false,
  });
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    assert.ok(gaps.includes(`UNFILLED:${key}`), key);
  }
  assert.ok(gaps.includes("REFUSE_SCRIPT"));
  assert.ok(gaps.includes("IN_PLACE_COMPLETION_FORBIDDEN"));
  assert.ok(gaps.includes("FOUNDER_EXECUTION_AUTHORIZATION"));
  assert.ok(gaps.includes("COPIED_AUTHORIZATION"));
});

test("a copied named checklist still gaps while the refuse script exits 2", () => {
  const fields = {};
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    fields[key] = `named-${key}`;
  }
  const gaps = executionAuthGaps({
    fields,
    inPlaceCompletion: false,
    refuseExit: 2,
    founderStatus: "AUTHORIZED",
    customerHost: "FORBIDDEN",
    credentials: "NONE",
    evidenceTiers: [],
    copiedAuthorization: true,
  });
  assert.deepEqual(gaps, ["REFUSE_SCRIPT"]);
});

test("in-place names stay a gap after the refuse script is imagined replaced", () => {
  const fields = {};
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    fields[key] = `named-${key}`;
  }
  const gaps = executionAuthGaps({
    fields,
    inPlaceCompletion: true,
    refuseExit: 0,
    founderStatus: "AUTHORIZED",
    customerHost: "FORBIDDEN",
    credentials: "NONE",
    evidenceTiers: [],
    copiedAuthorization: true,
  });
  assert.deepEqual(gaps, ["IN_PLACE_COMPLETION_FORBIDDEN"]);
});

test("gap function can return empty without starting a host", () => {
  const fields = {};
  for (const key of Object.keys(CHECKLIST_FIELDS)) {
    fields[key] = `named-${key}`;
  }
  const gaps = executionAuthGaps({
    fields,
    inPlaceCompletion: false,
    refuseExit: 0,
    founderStatus: "AUTHORIZED",
    customerHost: "FORBIDDEN",
    credentials: "NONE",
    evidenceTiers: [],
    copiedAuthorization: true,
  });
  assert.deepEqual(gaps, []);
  const blocked = run(READINESS_CLI, ["--execute"]);
  assert.equal(blocked.status, 2);
  assert.equal(blocked.stdout, `${EXECUTION_BLOCKED}\n`);
});

test("readiness sources stay off the host command path", () => {
  const lib = readFileSync(join(PACKET_DIR, "scripts", "readiness-lib.mjs"), "utf8");
  const cli = readFileSync(READINESS_CLI, "utf8");
  const combined = `${lib}\n${cli}`;
  for (const needle of ["apt-get", "npm publish", "pnpm", "ssh", "twine", "node:http", "node:https"]) {
    assert.equal(combined.includes(needle), false, needle);
  }
  const body = lib.slice(lib.indexOf("export function runCli"));
  const blockedAt = body.indexOf("executionRequested(");
  const exitAt = body.indexOf("process.exit(2)");
  const loadAt = body.indexOf("loadState(");
  assert.ok(blockedAt !== -1 && exitAt !== -1 && loadAt !== -1);
  assert.ok(blockedAt < exitAt && exitAt < loadAt);
});
