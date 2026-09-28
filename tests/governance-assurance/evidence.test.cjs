"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");
const api = require("../../packages/governance-assurance/src/index.cjs");

function byTrack(bindings, track) {
  const found = bindings.find((binding) => binding.track_id === track);
  assert.ok(found, track);
  return found;
}

test("wave 2 bindings keep unresolved tracks off the satisfied set", () => {
  const bindings = api.loadEvidence(root);
  assert.equal(bindings.length, 25);
  const ingress = byTrack(bindings, "T5");
  const egress = byTrack(bindings, "T6");
  assert.equal(ingress.wave2_state, "MERGED_OBSERVE_ONLY_LOADER_UNTOUCHED");
  assert.equal(ingress.artifact_status, "PRESENT");
  assert.equal(ingress.counts_toward_satisfaction, false);
  assert.deepEqual(ingress.count_control_ids, []);
  assert.equal(egress.wave2_state, "MERGED_CONTRACT_ONLY_HOST_NETWORK_NOT_EXECUTED");
  assert.equal(egress.artifact_status, "PRESENT");
  assert.equal(egress.counts_toward_satisfaction, false);
  assert.deepEqual(egress.count_control_ids, []);
  const unitE = byTrack(bindings, "UNIT-E");
  assert.equal(unitE.wave2_state, "MERGED_NO_LIVE_INTEGRATION");
  assert.equal(unitE.counts_toward_satisfaction, false);
  assert.deepEqual(unitE.count_control_ids, []);
  const o7 = byTrack(bindings, "T3");
  assert.equal(o7.verification_result, "O7_NOT_AUTHORIZED_DECISION_9_UNRESOLVED_BLOCKED_NODE");
  assert.equal(o7.counts_toward_satisfaction, false);
  const clean = byTrack(bindings, "T10");
  assert.equal(clean.verification_result, "BLOCKED_INFRA_EVIDENCE_UNSET");
  assert.equal(clean.freshness, "UNSET");
  assert.equal(clean.counts_toward_satisfaction, false);
  const stranger = byTrack(bindings, "T16");
  assert.equal(stranger.verification_result, "EXECUTION_NOT_AUTHORIZED");
  assert.equal(stranger.counts_toward_satisfaction, false);
  const demo = byTrack(bindings, "T11");
  assert.equal(demo.proof_class, "NOT_COMPLIANCE_ELIGIBLE");
  assert.equal(demo.counts_toward_satisfaction, false);
  const bench = byTrack(bindings, "BENCHMARK");
  assert.equal(bench.wave2_state, "DESIGN_TARGET");
  assert.equal(bench.counts_toward_satisfaction, false);
  const unitd = byTrack(bindings, "UNIT-D");
  assert.equal(unitd.verification_result, "UNIT_D_PROVED_NOT_SHIPPED");
  assert.equal(unitd.counts_toward_satisfaction, false);
  const host = byTrack(bindings, "T7");
  assert.equal(host.wave2_state, "CONTRACT_ONLY");
  assert.equal(host.counts_toward_satisfaction, false);
  const sequential = byTrack(bindings, "T8");
  assert.equal(sequential.verification_result, "EVALUATE_ONLY_HOST_ATTACHMENT_FALSE");
  assert.deepEqual(sequential.count_control_ids, ["GA-17", "GA-30"]);
  const progressive = byTrack(bindings, "T9");
  assert.equal(progressive.verification_result, "IN_PROCESS_HOST_ATTACHMENT_NOT_PERFORMED");
  assert.deepEqual(progressive.count_control_ids, ["GA-31"]);
  const health = byTrack(bindings, "T4");
  assert.equal(health.wave2_state, "IMPLEMENTED_INTERNAL");
  assert.deepEqual(health.count_control_ids, ["GA-28"]);
  const otlp = byTrack(bindings, "T12");
  assert.equal(otlp.verification_result, "DEFAULT_DISABLED_NOT_OPERATIONAL");
  assert.equal(otlp.counts_toward_satisfaction, false);
  assert.deepEqual(otlp.count_control_ids, []);
  const enterprise = byTrack(bindings, "T13");
  assert.equal(enterprise.verification_result, "NO_LIVE_CUSTOMER_AUTHORITY");
  const ws11 = byTrack(bindings, "T14");
  assert.equal(ws11.verification_result, "CHARACTERIZED_FORMAL_CLAIMS_NOT_CLAIMED");
  const python = byTrack(bindings, "T1");
  assert.equal(python.counts_toward_satisfaction, true);
  assert.equal(python.independent_verifier, "UNSET");
  assert.deepEqual(python.control_ids, ["GA-20"]);
  assert.deepEqual(python.count_control_ids, ["GA-20"]);
  assert.equal(python.limitations.some((line) => line.includes("NOT_REEXECUTED")), true);
  assert.equal(python.limitations.some((line) => line.includes("formal_slsa_claim is false")), true);
});

test("present artifacts are hashed and a missing file does not count", () => {
  const bindings = api.loadEvidence(root);
  const cli = byTrack(bindings, "CLI");
  const record = cli.artifact_records[0];
  const actual = crypto.createHash("sha256").update(fs.readFileSync(path.join(root, record.path))).digest("hex");
  assert.equal(record.sha256, actual);
  const missing = api.hydrateBinding({
    ...cli,
    artifacts: ["docs/internal/governance-assurance/missing-overlay.json"],
    counts_toward_satisfaction: true,
    count_control_ids: ["GA-01"],
  }, root);
  assert.equal(missing.artifact_status, "MISSING");
  assert.equal(missing.counts_toward_satisfaction, false);
  assert.equal(missing.verification_result, "ARTIFACT_MISSING");
});

test("rejected sole proofs and producer self-verification cannot count", () => {
  for (const kind of api.REJECTED_SOLE_PROOFS) {
    assert.equal(api.soleProofAdmissible(kind), false);
  }
  const control = api.CONTROLS.find((item) => item.control_id === "GA-12");
  const dashboard = {
    counts_toward_satisfaction: true,
    count_control_ids: ["GA-12"],
    sole_proof_kinds: ["DASHBOARD_GREEN"],
    artifact_status: "PRESENT",
    freshness: "CURRENT_FOR_CATALOG_REVIEW",
    proof_class: "PRODUCER_TEST",
    independent_verifier: "someone-else",
    producer: "producer",
  };
  assert.equal(api.bindingCountsFor(dashboard, control), false);
  const self = {
    ...dashboard,
    sole_proof_kinds: [],
    independent_verifier: "producer",
    producer: "producer",
  };
  const promoted = { ...control, verification_state: "INDEPENDENTLY_TESTED" };
  assert.equal(api.bindingCountsFor(self, promoted), false);
});
