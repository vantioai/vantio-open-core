"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../packages/governance-assurance/src/index.cjs");

test("six frameworks are version-pinned and unknown versions fail closed", () => {
  assert.equal(api.FRAMEWORKS.length, 6);
  const ids = api.FRAMEWORKS.map((framework) => framework.framework_id);
  assert.deepEqual(ids, [
    "NIST-AI-RMF",
    "NIST-AI-RMF-PLAYBOOK",
    "NIST-AI-AGENT-STANDARDS",
    "EU-AI-ACT",
    "ISO-IEC-42001",
    "US-FEDERAL-AI-ACQUISITION",
  ]);
  const current = api.selectMappings("NIST-AI-RMF", "1.0");
  assert.equal(current.ok, true);
  assert.equal(current.active, true);
  assert.equal(current.mappings.length, 40);
  const unknown = api.selectMappings("NIST-AI-RMF", "9.9");
  assert.equal(unknown.ok, false);
  assert.equal(unknown.reason, "UNKNOWN_FRAMEWORK_VERSION");
  assert.deepEqual(unknown.mappings, []);
  const missing = api.selectMappings("NOT-A-FRAMEWORK", "1.0");
  assert.equal(missing.reason, "UNKNOWN_FRAMEWORK");
});

test("every mapping carries provenance and does not copy clause text", () => {
  assert.equal(api.MAPPINGS.length, 144);
  for (const mapping of api.MAPPINGS) {
    assert.equal(mapping.mapping_version, "0.1.0-internal");
    assert.equal(mapping.mapping_commit, "NOT_SELF_HASHED");
    assert.equal(mapping.reviewer, "PENDING_INDEPENDENT_COUNCIL");
    assert.equal(typeof mapping.publication_date, "string");
    assert.equal(mapping.effective_date === "UNKNOWN" || typeof mapping.effective_date === "string", true);
    assert.equal(mapping.source_url.startsWith("http"), true);
    assert.equal(mapping.clause_text, null);
    assert.equal(mapping.vantio_fulfills_function, false);
    assert.equal(mapping.legal_classification, "NOT_A_LEGAL_CLASSIFICATION");
    assert.equal(/The organization shall/i.test(mapping.relationship_note), false);
    assert.equal(mapping.relationship_note.length <= api.LIMITS.maxString, true);
  }
  const iso = api.MAPPINGS.filter((mapping) => mapping.framework_id === "ISO-IEC-42001");
  assert.equal(iso.length, 40);
  assert.equal(iso.every((mapping) => mapping.reference === "SOURCE_ACCESS_REQUIRED"), true);
  assert.equal(iso.every((mapping) => mapping.source_access === "SOURCE_ACCESS_REQUIRED"), true);
  const controlIds = api.CONTROLS.map((control) => control.control_id);
  assert.deepEqual(api.unmappedControls("ISO-IEC-42001", "2023", controlIds), []);
  const isoDoc = api.FRAMEWORKS.find((framework) => framework.framework_id === "ISO-IEC-42001").documents[0];
  assert.match(isoDoc.notes, /unmapped list is empty/);
  assert.match(isoDoc.notes, /not a clause map/);
});

test("superseded federal memoranda stay visible and inactive", () => {
  const old = api.selectMappings("US-FEDERAL-AI-ACQUISITION", "M-24-10");
  assert.equal(old.ok, true);
  assert.equal(old.active, false);
  assert.equal(old.reason, "SUPERSEDED");
  assert.equal(old.superseded_by, "M-25-21");
  assert.equal(old.mappings.length, 1);
  const current = api.selectMappings("US-FEDERAL-AI-ACQUISITION", "M-25-21");
  assert.equal(current.active, true);
  const federal = api.FRAMEWORKS.find((framework) => framework.framework_id === "US-FEDERAL-AI-ACQUISITION");
  const memo2410 = federal.documents.find((document) => document.version === "M-24-10");
  const memo2418 = federal.documents.find((document) => document.version === "M-24-18");
  assert.match(memo2410.source_url, /M-25-21/);
  assert.match(memo2418.source_url, /M-25-22/);
  assert.match(memo2410.notes, /successor PDF/);
  assert.match(memo2418.notes, /successor PDF/);
});

test("mapping walk is bounded", () => {
  const start = api.MAPPINGS.find((mapping) => mapping.mapping_id === "MAP-PLAY-GA-01");
  const chain = api.walkMappings(start.mapping_id);
  assert.equal(chain.length, 2);
  const cyclic = [
    { mapping_id: "A", related_mapping_ids: ["B"] },
    { mapping_id: "B", related_mapping_ids: ["A"] },
  ];
  assert.throws(() => api.walkMappings("A", cyclic), /MAPPING_CYCLE/);
  const deep = [];
  for (let index = 0; index < 20; index += 1) {
    deep.push({ mapping_id: `N${index}`, related_mapping_ids: index < 19 ? [`N${index + 1}`] : [] });
  }
  assert.throws(() => api.walkMappings("N0", deep), /MAPPING_DEPTH_EXCEEDED/);
});
