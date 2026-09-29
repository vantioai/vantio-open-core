"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");
const api = require("../../packages/governance-assurance/src/index.cjs");
const rebind = require("../../docs/internal/governance-assurance/stage-b/C6-REBIND.json");

const CATALOG_ROWS = ["GA-04", "GA-21", "GA-22", "GA-35", "GA-37", "GA-38", "GA-39"];
const OPEN_GATE_IDS = [
  "GATE-F-BILLING",
  "GATE-F-C8",
  "GATE-I-RECORDINGS",
  "GATE-RBK004-LIVE",
  "GATE-CLASS-B",
];

function control(id) {
  const found = api.CONTROLS.find((item) => item.control_id === id);
  assert.ok(found, id);
  return found;
}

test("catalog-owned rows supersede 0.1.0-internal and product pins do not", () => {
  assert.equal(api.PACKAGE_VERSION, "0.2.0-internal");
  assert.equal(api.CATALOG_VERSION, "0.2.0-internal");
  assert.equal(api.MAPPING_VERSION, "0.2.0-internal");
  assert.equal(api.SUPERSEDES_PACKAGE, "0.1.0-internal");
  assert.equal(api.REVIEW_DATE, "2026-09-28");
  assert.equal(api.SOURCE_BASE_COMMIT, "b0bcbdeb01ccb84a58a3aa6aacd0c05f94b22450");
  assert.equal(api.PROGRAM_CLAIM_CEILING, "INTERNAL_CLEAN_HOST_PROOF");
  assert.equal(api.REVIEWER, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(api.MAPPING_COMMIT, "NOT_SELF_HASHED");
  for (const id of CATALOG_ROWS) {
    const row = control(id);
    assert.equal(row.capability_version, "0.2.0-internal", id);
    assert.equal(row.supersedes, "0.1.0-internal", id);
    assert.equal(row.review_date, "2026-09-28", id);
  }
  const cli = control("GA-01");
  assert.equal(cli.capability_version, "0.3.24");
  assert.equal(cli.supersedes, null);
  const python = control("GA-20");
  assert.equal(python.capability_version, "3.1.0");
  assert.equal(python.supersedes, null);
  for (const row of api.CONTROLS) {
    assert.equal(api.PROMOTION_BLOCKED_VERIFICATION.includes(row.verification_state), false, row.control_id);
  }
});

test("Stage B and C5 citations stay visible and do not satisfy open rows", () => {
  const bindings = api.loadEvidence(root);
  const stage = bindings.find((binding) => binding.binding_id === "EB-STAGE-B");
  const c5 = bindings.find((binding) => binding.binding_id === "EB-C5");
  const residual = bindings.find((binding) => binding.binding_id === "EB-WAVE2-RESIDUAL");
  assert.equal(stage.counts_toward_satisfaction, false);
  assert.equal(stage.verification_result, "PARTIAL_INTERNAL_CLEAN_HOST_PROOF");
  assert.equal(stage.wave2_state, "STAGE_B_PARTIAL_CITED_NOT_REEXECUTED");
  assert.equal(stage.artifact_status, "PRESENT");
  assert.equal(c5.counts_toward_satisfaction, false);
  assert.equal(c5.wave2_state, "C5_INTEGRATION_PASS_WITH_NONBLOCKING_AND_OPEN_GATES");
  assert.equal(c5.artifact_status, "PRESENT");
  assert.equal(residual.counts_toward_satisfaction, false);
  assert.equal(residual.verification_result, "ENFORCEMENT_NOT_PROVED_RBK004_SOURCE_CLOSED_LIVE_REPROOF_NOT_CLAIMED");
  assert.deepEqual(residual.count_control_ids, []);
  assert.equal(stage.control_ids.includes("GA-24"), false);
  assert.equal(c5.control_ids.includes("GA-24"), false);
  const facts = rebind.program_bindings;
  assert.equal(facts.stage_b, "PARTIAL_INTERNAL_CLEAN_HOST_PROOF");
  assert.equal(facts.installer, "VANTIO_INSTALLER_REPEATABLE_PATH_PROVED_WITH_LIMITATIONS");
  assert.equal(facts.installer_not_yet, "VANTIO_INSTALLER_INTERNAL_CUSTOMER_CANDIDATE");
  assert.equal(facts.claim_ceiling, "INTERNAL_CLEAN_HOST_PROOF");
  assert.equal(facts.rbk_004, "SOURCE_CLOSED_MERGED");
  assert.equal(facts.rbk_004_live_class_a_reproof, "NOT_YET_AUTHORIZED");
  assert.equal(facts.live_reproof_claimed, false);
  assert.equal(facts.billing_close, "STAGE_B_BILLING_CLOSE_PENDING");
  assert.equal(facts.council_f, "NEEDS_REVISION");
  assert.equal(facts.recordings_a_h, "NOT_CAPTURED");
  assert.equal(facts.council_i, "NEEDS_REVISION");
  assert.equal(facts.enforcement_efficacy, "NOT_PROVED");
  assert.equal(facts.c8, "DESIGN_COMPLETE_AWAITING_FOUNDER_CREDENTIAL_OR_ROLE");
  assert.equal(facts.c8_short, "DESIGN_COMPLETE_AWAITING_FOUNDER");
  assert.equal(facts.c8_ready, false);
  assert.equal(facts.class_b, "BLOCKED");
  assert.equal(facts.next_lab, "NOT_YET_AUTHORIZED");
  assert.equal(facts.public_rewrite, "HOLD");
  assert.equal(facts.destruction, "STAGE_B_DESTROY_PASS");
  assert.equal(facts.frozen_pins["@vantio/cli"], "0.3.24");
  assert.equal(facts.frozen_pins["@vantio/agent-sdk"], "0.2.4");
  assert.equal(facts.frozen_pins["vantio-agent-sdk"], "3.1.0");
  assert.equal(facts.qualifies_for_0_3_0, false);
  assert.equal(facts.qualifies_for_customer_candidate, false);
  assert.deepEqual(rebind.open_gates.map((gate) => gate.id), OPEN_GATE_IDS);
  assert.equal(rebind.tally.clean_pass, 0);
  assert.equal(rebind.tally.needs_revision, 2);
  const posture = api.buildReports({ root })["GOVERNANCE_POSTURE.json"];
  assert.deepEqual(posture.open_gates.map((gate) => gate.id), OPEN_GATE_IDS);
  assert.equal(posture.program_bindings.billing_close, "STAGE_B_BILLING_CLOSE_PENDING");
  assert.equal(posture.rebind_not_claimed.includes("0.3.0"), true);
  assert.equal(posture.rebind_not_claimed.includes("1.0.0-customer-candidate"), true);
  for (const id of ["GA-13", "GA-14", "GA-15", "GA-27", "GA-33", "GA-34", "GA-40"]) {
    const result = api.satisfactionFor(control(id), bindings);
    assert.equal(result.pass, false, id);
    assert.equal(result.status, "NOT_SATISFIED", id);
  }
  const joined = JSON.stringify(posture.program_bindings);
  assert.equal(joined.includes("\"PASS\""), false);
});

test("installer denylist and frozen packages stay untouched", () => {
  const constants = fs.readFileSync(path.join(root, "packages/vantio-install/vantio_install/constants.py"), "utf8");
  assert.match(constants, /PROOF_CEILING = "INTERNAL_CLEAN_HOST_PROOF"/);
  assert.match(constants, /PROOF_STATE = "NOT_PROVED"/);
  assert.match(constants, /GA_0\.2\.0_internal_rebind_completed/);
  const cli = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-cli/package.json"), "utf8"));
  const npmSdk = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-agent-sdk/package.json"), "utf8"));
  assert.equal(cli.version, "0.3.24");
  assert.equal(npmSdk.version, "0.2.4");
});
}
