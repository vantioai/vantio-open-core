"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");
const api = require("../../packages/governance-assurance/src/index.cjs");

const REQUIRED_PROVENANCE = [
  "package_version",
  "catalog_version",
  "mapping_version",
  "mapping_commit",
  "source_repository",
  "source_base_commit",
  "reviewer",
  "retrieved_at",
  "generated_at",
  "audience",
  "distribution",
  "generator",
];

test("reports are deterministic and carry no compliance verdict", () => {
  const first = api.buildReports({ root });
  const second = api.buildReports({ root });
  assert.equal(api.canonicalize(first), api.canonicalize(second));
  const posture = first["GOVERNANCE_POSTURE.json"];
  for (const key of REQUIRED_PROVENANCE) {
    assert.equal(typeof posture.provenance[key], "string");
    assert.equal(posture.provenance[key].length > 0, true);
  }
  assert.equal(posture.provenance.package_version, "0.2.0-internal");
  assert.equal(posture.provenance.self_certified_council_pass, false);
  assert.equal(posture.overall_compliance_score, undefined);
  assert.equal(posture.controls.every((row) => row.satisfaction.pass === false), true);
  assert.equal(posture.controls.some((row) => row.satisfaction.status === "PASS"), false);
  assert.equal(posture.provenance.program_claim_ceiling, "INTERNAL_CLEAN_HOST_PROOF");
  assert.equal(posture.provenance.supersedes_package, "0.1.0-internal");
  assert.equal(posture.program_bindings.stage_b, "PARTIAL_INTERNAL_CLEAN_HOST_PROOF");
  const names = Object.keys(first);
  for (const name of [
    "GOVERNANCE_POSTURE.json",
    "GOVERNANCE_POSTURE.md",
    "CUSTOMER_RESPONSIBILITY_MATRIX.json",
    "CONTROL_EVIDENCE_INDEX.json",
    "FRAMEWORK_VERSION_REGISTER.json",
    "UNSUPPORTED_AND_EXTERNAL_CONTROLS.json",
    "PROCUREMENT_EVIDENCE_INDEX.json",
    "VERIFICATION_INSTRUCTIONS.md",
  ]) {
    assert.equal(names.includes(name), true);
  }
  assert.equal(api.claimProblems(first).length, 0);
});

test("planned, missing, stale, and demo evidence cannot become a pass", () => {
  const bindings = api.loadEvidence(root);
  const byId = Object.fromEntries(api.CONTROLS.map((control) => [control.control_id, control]));
  for (const id of ["GA-05", "GA-08", "GA-13", "GA-14", "GA-15", "GA-29", "GA-33", "GA-34", "GA-40"]) {
    const result = api.satisfactionFor(byId[id], bindings);
    assert.equal(result.pass, false);
    assert.equal(result.status, "NOT_SATISFIED");
  }
  const fresh = byId["GA-01"];
  const stale = api.satisfactionFor(fresh, bindings, { triggers: ["EVIDENCE_EXPIRED"] });
  assert.equal(stale.reason, "STALE");
  assert.equal(stale.prior_pass, "CLEARED");
  assert.equal(stale.pass, false);
  const demoOnly = bindings.filter((binding) => binding.track_id === "T11");
  const demoResult = api.satisfactionFor(byId["GA-39"], demoOnly);
  assert.equal(demoResult.status, "NOT_SATISFIED");
  const unset = { ...fresh, evidence_freshness: "UNSET" };
  assert.equal(api.satisfactionFor(unset, bindings).reason, "STALE");
});

test("responsibility matrix keeps legal duties off Vantio and shows every customer row", () => {
  const matrix = api.buildMatrix();
  assert.equal(matrix.customer_org_structure, "NOT_ASSERTED");
  assert.equal(matrix.rows.length, 40);
  for (const row of matrix.rows) {
    const control = api.CONTROLS.find((item) => item.control_id === row.control_id);
    if (control.domain === "LEGAL" || control.domain === "PRIVACY") {
      assert.notEqual(row.raci.VANTIO, "ACCOUNTABLE");
    }
    if (control.domain === "LEGAL") assert.equal(row.raci.VANTIO, "NOT_APPLICABLE");
  }
  assert.equal(api.customerResponsibilityCount(matrix) > 0, true);
  const overridden = api.applyOverrides(matrix, { "GA-05": { CUSTOMER_SECURITY: "ACCOUNTABLE" } });
  assert.equal(overridden.rows.find((row) => row.control_id === "GA-05").raci.CUSTOMER_SECURITY, "ACCOUNTABLE");
  assert.equal(overridden.customer_org_structure, "NOT_ASSERTED");
  assert.throws(() => api.applyOverrides(matrix, { "GA-05": { CUSTOMER_DEPARTMENT_X: "ACCOUNTABLE" } }), /unknown role/);
});

test("public disclosure withholds the catalog and procurement is not submitted", () => {
  const reports = api.buildReports({ root });
  const pub = reports["PUBLIC_DISCLOSURE.json"];
  assert.equal(pub.distribution, "PUBLIC");
  assert.equal(pub.detail, "CONTROL_DETAIL_WITHHELD");
  assert.equal(JSON.stringify(pub).includes("BLOCKED_INFRA"), false);
  assert.equal(JSON.stringify(pub).includes("bc-"), false);
  const procurement = reports["PROCUREMENT_EVIDENCE_INDEX.json"];
  assert.equal(procurement.submission_status, "NOT_SUBMITTED");
  assert.equal(procurement.proof_class_elevated, false);
  assert.equal(procurement.distribution, "INTERNAL_RESTRICTED");
  const register = reports["FRAMEWORK_VERSION_REGISTER.json"];
  const federal = register.frameworks.find((item) => item.framework_id === "US-FEDERAL-AI-ACQUISITION");
  assert.equal(federal.documents.some((document) => document.version === "M-24-10" && document.superseded_status === "SUPERSEDED"), true);
  const unsupported = reports["UNSUPPORTED_AND_EXTERNAL_CONTROLS.json"];
  assert.equal(unsupported.unsupported_control_count, 14);
  assert.equal(unsupported.external_control_count, 9);
});

test("framework views match the generator", () => {
  const views = {
    "nist-ai-rmf.md": "NIST-AI-RMF",
    "eu-ai-act.md": "EU-AI-ACT",
    "iso-iec-42001.md": "ISO-IEC-42001",
    "us-federal.md": "US-FEDERAL-AI-ACQUISITION",
  };
  for (const [name, id] of Object.entries(views)) {
    const text = fs.readFileSync(path.join(root, "docs/internal/governance-assurance/views", name), "utf8");
    assert.equal(text, api.renderFramework(id));
    assert.match(text, /does not fulfill/);
  }
  const iso = fs.readFileSync(path.join(root, "docs/internal/governance-assurance/views/iso-iec-42001.md"), "utf8");
  assert.match(iso, /SOURCE_ACCESS_REQUIRED/);
  assert.equal(iso.includes("The organization shall"), false);
});

test("committed reports match a fresh generation", () => {
  const dir = path.join(root, "docs/internal/governance-assurance/reports");
  const fresh = api.buildReports({ root });
  for (const name of Object.keys(fresh)) {
    const text = fs.readFileSync(path.join(dir, name), "utf8");
    const expected = typeof fresh[name] === "string" ? fresh[name] : api.stableStringify(fresh[name]);
    assert.equal(text, expected, name);
  }
});
