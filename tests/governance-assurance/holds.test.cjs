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

function control(id) {
  const found = api.CONTROLS.find((item) => item.control_id === id);
  assert.ok(found, id);
  return found;
}

test("EB-T1 custody record cannot satisfy GA-12 or GA-19", () => {
  const bindings = api.loadEvidence(root);
  const python = bindings.find((binding) => binding.binding_id === "EB-T1");
  const ga12 = control("GA-12");
  const ga19 = control("GA-19");
  const ga20 = control("GA-20");
  assert.equal(ga12.evidence_artifacts.includes("EB-T1"), false);
  assert.equal(ga19.evidence_artifacts.includes("EB-T1"), false);
  assert.equal(ga12.proof_class === "RELEASE_CLOSE_PACKET", false);
  assert.equal(ga19.proof_class === "RELEASE_CLOSE_PACKET", false);
  assert.equal(ga20.evidence_artifacts.includes("EB-T1"), true);
  assert.equal(ga20.proof_class, "RELEASE_CLOSE_PACKET");
  assert.match(ga20.limitations.join("\n"), /CITED_PRIOR_VALID/);
  assert.match(ga20.limitations.join("\n"), /formal_slsa_claim is false/);
  assert.match(python.limitations.join("\n"), /NOT_REEXECUTED/);
  const widened = {
    ...python,
    control_ids: ["GA-12", "GA-19", "GA-20"],
    count_control_ids: ["GA-12", "GA-19", "GA-20"],
    counts_toward_satisfaction: true,
  };
  assert.equal(api.custodyOnlyReleaseClose(widened), true);
  assert.equal(api.bindingCountsFor(widened, ga12), false);
  assert.equal(api.bindingCountsFor(widened, ga19), false);
  assert.equal(api.bindingCountsFor(widened, ga20), true);
  for (const row of [ga12, ga19]) {
    const sole = api.satisfactionFor(row, [widened]);
    assert.equal(sole.pass, false);
    assert.equal(sole.status, "NOT_SATISFIED");
    assert.equal(sole.binding_ids, undefined);
    const live = api.satisfactionFor(row, bindings);
    assert.equal(live.pass, false);
    assert.equal((live.binding_ids || []).includes("EB-T1"), false);
  }
  const custody = api.satisfactionFor(ga20, [python]);
  assert.equal(custody.pass, false);
  assert.deepEqual(custody.binding_ids, ["EB-T1"]);
});

test("a version file alone cannot satisfy GA-24, and the URL-path exception stays visible", () => {
  const bindings = api.loadEvidence(root);
  const ga24 = control("GA-24");
  const manual = fs.readFileSync(path.join(root, "docs/products/optics/USER-MANUAL.md"), "utf8");
  assert.match(manual, /A secret placed in the URL path is stored, because the path is kept/);
  const visible = [...ga24.limitations, ...ga24.unsupported_paths, ga24.claim_ceiling].join("\n");
  assert.match(visible, /URL path/);
  assert.match(visible, /stored/);
  assert.match(visible, /package\.json does not establish credential non-collection/);
  assert.equal(ga24.evidence_artifacts.includes("EB-CLI-0324"), false);
  assert.equal(ga24.verification_state, "NOT_TESTED");
  const cli = bindings.find((binding) => binding.binding_id === "EB-CLI-0324");
  assert.equal(cli.control_ids.includes("GA-24"), false);
  assert.equal(api.bindingCountsFor(cli, ga24), false);
  const versionOnly = {
    binding_id: "EB-VERSION-ONLY",
    counts_toward_satisfaction: true,
    count_control_ids: ["GA-24"],
    artifacts: ["packages/vantio-cli/package.json"],
    artifact_status: "PRESENT",
    freshness: "CURRENT_FOR_CATALOG_REVIEW",
    proof_class: "PRODUCER_TEST",
    independent_verifier: "UNSET",
    producer: "published @vantio/cli",
    sole_proof_kinds: [],
  };
  assert.equal(api.versionFileOnly(versionOnly), true);
  assert.equal(api.bindingCountsFor(versionOnly, ga24), false);
  const versionResult = api.satisfactionFor(ga24, [versionOnly]);
  assert.equal(versionResult.pass, false);
  assert.equal(versionResult.status, "NOT_SATISFIED");
  assert.equal(versionResult.binding_ids, undefined);
  const pyprojectOnly = {
    ...versionOnly,
    artifacts: ["packages/vantio-agent-sdk-py/pyproject.toml"],
  };
  assert.equal(api.versionFileOnly(pyprojectOnly), true);
  assert.equal(api.bindingCountsFor(pyprojectOnly, ga24), false);
  const privacy = bindings.find((binding) => binding.binding_id === "EB-OPTICS-PRIVACY");
  assert.equal(privacy.counts_toward_satisfaction, false);
  assert.match(privacy.limitations.join("\n"), /URL path/);
  const live = api.satisfactionFor(ga24, bindings);
  assert.equal(live.pass, false);
  assert.equal(live.status, "NOT_SATISFIED");
  assert.equal(live.binding_ids, undefined);
});

test("merged ingress, egress, and Unit E stay off satisfaction", () => {
  const bindings = api.loadEvidence(root);
  const ingressSrc = fs.readFileSync(path.join(root, "packages/pe-ingress-authority/src/constants.cjs"), "utf8");
  const egressSrc = fs.readFileSync(path.join(root, "packages/pe-egress-authority/src/decision.cjs"), "utf8");
  const markers = JSON.parse(fs.readFileSync(path.join(root, "docs/internal/optics-pkg02-unit-e/MATRIX-MARKERS.json"), "utf8"));
  assert.match(ingressSrc, /OBSERVE_ONLY/);
  assert.match(egressSrc, /this_force_executed_host: false/);
  assert.match(egressSrc, /this_force_executed_network: false/);
  assert.equal(markers.activates_unit_e, true);
  assert.equal(markers.merged, false);
  assert.equal(markers.registry_publish, false);
  assert.equal(markers.sealed, false);
  const posture = api.buildReports({ root })["GOVERNANCE_POSTURE.json"];
  assert.match(posture.claim_ceiling, /NON-NORMATIVE/);
  assert.match(posture.claim_ceiling, /NOT_LEGAL_ADVICE/);
  assert.match(posture.claim_ceiling, /NO_COMPLIANCE_GUARANTEE/);
  for (const row of posture.controls) {
    assert.equal(row.satisfaction.pass, false);
    const ids = row.satisfaction.binding_ids || [];
    assert.equal(ids.includes("EB-T5"), false);
    assert.equal(ids.includes("EB-T6"), false);
    assert.equal(ids.includes("EB-UNIT-E"), false);
    assert.equal(ids.includes("EB-OPTICS-PRIVACY"), false);
    if (row.control_id === "GA-14" || row.control_id === "GA-15") {
      assert.equal(row.satisfaction.status, "NOT_SATISFIED");
    }
  }
});
}
